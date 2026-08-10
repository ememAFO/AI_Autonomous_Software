"""Explicitly import Stage 4G verified first-party evidence."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from src.hermes.validation_evidence_log import (
    ValidationEvidenceLog,
    ValidationEvidenceLogError,
)
from src.hermes.validation_evidence_summary import (
    ValidationEvidenceSummarizer,
)
from src.research.first_party_validation_storage import (
    ControlledJsonlStore,
    FirstPartyImportRegistry,
    FirstPartyVerifiedStore,
)


class FirstPartyImportError(ValueError):
    """Raised when Stage 4G evidence import fails closed."""


TOKEN_PATTERN = re.compile(r"^[A-Za-z0-9_.:-]{3,120}$")


@dataclass(frozen=True)
class FirstPartyImportResult:
    import_id: str
    resolution_id: str
    campaign_id: str
    import_reference: str
    imported: int
    target_log_path: str
    import_registry_path: str
    before_summary: dict[str, Any]
    after_summary: dict[str, Any]
    imported_source_references: tuple[str, ...]
    applied_at: str
    authorized_actions: dict[str, bool] = field(
        default_factory=lambda: {
            "validation_evidence_log_append": True,
        }
    )
    protected_actions: dict[str, bool] = field(
        default_factory=lambda: {
            "verified_intake_modified": False,
            "theme_state_modified": False,
            "build_approved": False,
            "public_action_taken": False,
            "automatic_outreach": False,
        }
    )


class FirstPartyImportService:
    """Preflight and append approved first-party evidence only."""

    RESOLUTION_ROOT = Path(
        "reports/research/first_party_review_resolutions"
    )
    REPORT_ROOT = Path(
        "reports/research/first_party_evidence_imports"
    )

    def __init__(
        self,
        *,
        verified_store: FirstPartyVerifiedStore | None = None,
        import_registry: FirstPartyImportRegistry | None = None,
    ) -> None:
        self.project_root = Path.cwd().resolve()
        self.resolution_root = (
            self.project_root / self.RESOLUTION_ROOT
        ).resolve()
        self.report_root = (
            self.project_root / self.REPORT_ROOT
        ).resolve()
        self.verified_store = (
            verified_store or FirstPartyVerifiedStore()
        )
        self.import_registry = (
            import_registry or FirstPartyImportRegistry()
        )

    def apply(
        self,
        *,
        resolution_file: str | Path,
        output_file: str | Path,
        import_reference: str,
        apply_changes: bool,
    ) -> FirstPartyImportResult:
        if not apply_changes:
            raise FirstPartyImportError(
                "Evidence import requires explicit apply_changes=True"
            )
        resolution_path = self._controlled_file(
            Path(resolution_file),
            root=self.resolution_root,
            suffix=".json",
            label="review resolution",
        )
        output_path = self._controlled_output(
            Path(output_file),
            root=self.report_root,
            suffix=".json",
            label="import report",
        )
        if output_path.exists():
            raise FirstPartyImportError(
                "Import report already exists and will not be overwritten"
            )

        resolution = self._load_object(resolution_path)
        resolution_id = self._required_text(
            "resolution_id",
            resolution.get("resolution_id", ""),
        )
        if self.import_registry.has_resolution(resolution_id):
            raise FirstPartyImportError(
                "Review resolution has already been imported"
            )
        audit_reference = self._audit_reference(import_reference)
        campaign_id = self._required_text(
            "campaign_id",
            resolution.get("campaign_id", ""),
        )
        verified_path = (
            self.project_root
            / self._required_text(
                "verified_intake_path",
                resolution.get("verified_intake_path", ""),
            )
        ).resolve()
        if not self._is_within(
            verified_path,
            self.verified_store.root,
        ):
            raise FirstPartyImportError(
                "Verified intake path is outside the controlled root"
            )
        if self._file_hash(verified_path) != str(
            resolution.get("verified_intake_hash", "")
        ):
            raise FirstPartyImportError(
                "Verified intake changed after review resolution"
            )
        records = self.verified_store.read(verified_path)
        if len(records) != int(resolution.get("approved", -1)):
            raise FirstPartyImportError(
                "Verified intake count does not match resolution"
            )
        if not records:
            raise FirstPartyImportError(
                "Resolution contains no approved evidence"
            )

        target_log_path = self._required_text(
            "target_log_path",
            records[0].get("target_log_path", ""),
        )
        theme = self._required_text(
            "theme",
            records[0].get("theme", ""),
        )
        for record in records:
            if str(record.get("resolution_id", "")) != resolution_id:
                raise FirstPartyImportError(
                    "Verified record resolution_id mismatch"
                )
            if str(record.get("campaign_id", "")) != campaign_id:
                raise FirstPartyImportError(
                    "Verified record campaign_id mismatch"
                )
            if str(record.get("target_log_path", "")) != target_log_path:
                raise FirstPartyImportError(
                    "Verified records disagree on target log"
                )
            if str(record.get("theme", "")) != theme:
                raise FirstPartyImportError(
                    "Verified records disagree on theme"
                )
            if str(record.get("source_trust", "")) != (
                ValidationEvidenceLog.HUMAN_ATTESTED_FIRST_PARTY
            ):
                raise FirstPartyImportError(
                    "Verified record does not have first-party trust"
                )

        target_log = ValidationEvidenceLog(
            log_path=target_log_path
        )
        before_entries = target_log.list_entries()
        existing_references = {
            entry.source_reference for entry in before_entries
        }
        duplicates = sorted(
            str(record.get("source_reference", ""))
            for record in records
            if str(record.get("source_reference", ""))
            in existing_references
        )
        if duplicates:
            raise FirstPartyImportError(
                "Verified evidence already exists in validation log: "
                f"{duplicates}"
            )

        self._preflight(records, target_log_path)
        target_path = Path(target_log_path).resolve()
        target_snapshot = ControlledJsonlStore.snapshot(target_path)
        registry_path = self.import_registry.path_for(campaign_id)
        registry_snapshot = ControlledJsonlStore.snapshot(
            registry_path
        )
        imported_references: list[str] = []
        try:
            for record in records:
                target_log.add_entry(
                    theme=self._required_text(
                        "theme",
                        record.get("theme", ""),
                    ),
                    validation_plan_path=self._required_text(
                        "validation_plan_path",
                        record.get("validation_plan_path", ""),
                    ),
                    evidence_type=self._required_text(
                        "evidence_type",
                        record.get("evidence_type", ""),
                    ),
                    evidence_summary=self._required_text(
                        "evidence_summary",
                        record.get("evidence_summary", ""),
                    ),
                    source_reference=self._required_text(
                        "source_reference",
                        record.get("source_reference", ""),
                    ),
                    signal_strength=self._required_text(
                        "signal_strength",
                        record.get("signal_strength", ""),
                    ),
                    supports_validation=bool(
                        record.get("supports_validation", False)
                    ),
                    source_trust=(
                        ValidationEvidenceLog
                        .HUMAN_ATTESTED_FIRST_PARTY
                    ),
                    notes=self._notes(record),
                )
                imported_references.append(
                    str(record["source_reference"])
                )

            summarizer = ValidationEvidenceSummarizer(target_log)
            before_summary = asdict(
                summarizer.summarize_entries(
                    theme=theme,
                    entries=[
                        entry
                        for entry in before_entries
                        if entry.theme.lower() == theme.lower()
                    ],
                )
            )
            after_summary = asdict(
                summarizer.summarize_theme(theme)
            )
            import_id = "FPI-" + uuid4().hex
            applied_at = datetime.now(UTC).isoformat()
            self.import_registry.append_many(
                registry_path,
                [
                    {
                        "import_id": import_id,
                        "resolution_id": resolution_id,
                        "campaign_id": campaign_id,
                        "import_reference": audit_reference,
                        "target_log_path": target_log_path,
                        "imported": len(records),
                        "source_references": imported_references,
                        "applied_at": applied_at,
                    }
                ],
            )
            result = FirstPartyImportResult(
                import_id=import_id,
                resolution_id=resolution_id,
                campaign_id=campaign_id,
                import_reference=audit_reference,
                imported=len(records),
                target_log_path=target_log_path,
                import_registry_path=self._project_path(
                    registry_path
                ),
                before_summary=before_summary,
                after_summary=after_summary,
                imported_source_references=tuple(
                    imported_references
                ),
                applied_at=applied_at,
            )
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(
                json.dumps(
                    asdict(result),
                    indent=2,
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )
            return result
        except Exception:
            ControlledJsonlStore.restore(
                target_path,
                target_snapshot,
            )
            ControlledJsonlStore.restore(
                registry_path,
                registry_snapshot,
            )
            if output_path.exists():
                output_path.unlink()
            raise

    def _preflight(
        self,
        records: list[dict[str, Any]],
        target_log_path: str,
    ) -> None:
        preflight_root = (
            self.project_root
            / "reports/intelligence/first_party_preflight"
        )
        preflight_root.mkdir(parents=True, exist_ok=True)
        preflight_path = (
            preflight_root / f"preflight-{uuid4().hex}.json"
        )
        target_path = Path(target_log_path).resolve()
        if target_path.exists():
            preflight_path.write_bytes(target_path.read_bytes())
        try:
            log = ValidationEvidenceLog(log_path=preflight_path)
            for record in records:
                log.add_entry(
                    theme=str(record["theme"]),
                    validation_plan_path=str(
                        record["validation_plan_path"]
                    ),
                    evidence_type=str(record["evidence_type"]),
                    evidence_summary=str(
                        record["evidence_summary"]
                    ),
                    source_reference=str(
                        record["source_reference"]
                    ),
                    signal_strength=str(
                        record["signal_strength"]
                    ),
                    supports_validation=bool(
                        record["supports_validation"]
                    ),
                    source_trust=(
                        ValidationEvidenceLog
                        .HUMAN_ATTESTED_FIRST_PARTY
                    ),
                    notes=self._notes(record),
                )
        except (
            OSError,
            ValidationEvidenceLogError,
            ValueError,
        ) as exc:
            raise FirstPartyImportError(
                "Verified evidence failed validation-log preflight"
            ) from exc
        finally:
            if preflight_path.exists():
                preflight_path.unlink()

    @staticmethod
    def _notes(record: dict[str, Any]) -> str:
        fields = [
            (
                "Imported through Stage 4G after explicit human review "
                "of sanitized first-party evidence."
            ),
            f"campaign_id={record.get('campaign_id', '')}",
            f"review_id={record.get('review_id', '')}",
            f"captured_at={record.get('captured_at', '')}",
            f"capture_reference={record.get('capture_reference', '')}",
            f"participant_role={record.get('participant_role', '')}",
            f"capture_method={record.get('capture_method', '')}",
            f"evidence_kind={record.get('evidence_kind', '')}",
            f"attestation_basis={record.get('attestation_basis', '')}",
            f"consent_version={record.get('consent_version', '')}",
            (
                "question_set_version="
                f"{record.get('question_set_version', '')}"
            ),
            f"action_confirmed={record.get('action_confirmed', False)}",
            f"measurement_count={record.get('measurement_count', '')}",
            f"measurement_window={record.get('measurement_window', '')}",
            f"candidate_hash={record.get('candidate_hash', '')}",
            f"resolution_id={record.get('resolution_id', '')}",
            "human_reviewed=true",
            "first_party_attested=true",
        ]
        return " ".join(fields)

    @staticmethod
    def _load_object(path: Path) -> dict[str, Any]:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise FirstPartyImportError(
                f"Could not read JSON object: {path}"
            ) from exc
        if not isinstance(payload, dict):
            raise FirstPartyImportError(
                "JSON file must contain an object"
            )
        return payload

    def _controlled_file(
        self,
        path: Path,
        *,
        root: Path,
        suffix: str,
        label: str,
    ) -> Path:
        resolved = path.resolve()
        if not self._is_within(resolved, root):
            raise FirstPartyImportError(
                f"{label} must stay inside {self._project_path(root)}"
            )
        if resolved.suffix != suffix or not resolved.is_file():
            raise FirstPartyImportError(
                f"{label} must be an existing {suffix} file"
            )
        return resolved

    def _controlled_output(
        self,
        path: Path,
        *,
        root: Path,
        suffix: str,
        label: str,
    ) -> Path:
        resolved = path.resolve()
        if not self._is_within(resolved, root):
            raise FirstPartyImportError(
                f"{label} must stay inside {self._project_path(root)}"
            )
        if resolved.suffix != suffix:
            raise FirstPartyImportError(
                f"{label} must use {suffix}"
            )
        return resolved

    def _project_path(self, path: Path) -> str:
        try:
            return str(path.resolve().relative_to(self.project_root))
        except ValueError as exc:
            raise FirstPartyImportError(
                "Path is outside the project root"
            ) from exc

    @staticmethod
    def _is_within(path: Path, root: Path) -> bool:
        try:
            path.relative_to(root)
            return True
        except ValueError:
            return False

    @staticmethod
    def _required_text(field_name: str, value: Any) -> str:
        if not isinstance(value, str) or not value.strip():
            raise FirstPartyImportError(
                f"{field_name} is required"
            )
        return " ".join(value.split())

    @staticmethod
    def _audit_reference(value: Any) -> str:
        if not isinstance(value, str) or not value.strip():
            raise FirstPartyImportError(
                "import_reference is required"
            )
        reference = value.strip()
        if not TOKEN_PATTERN.fullmatch(reference):
            raise FirstPartyImportError(
                "import_reference contains unsupported characters"
            )
        return reference

    @staticmethod
    def _file_hash(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(65_536), b""):
                digest.update(chunk)
        return digest.hexdigest()
