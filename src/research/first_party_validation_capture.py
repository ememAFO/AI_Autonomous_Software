"""Capture sanitized Stage 4G first-party validation candidates."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from src.hermes.validation_evidence_log import ValidationEvidenceLog
from src.research.first_party_validation_storage import (
    ControlledJsonlStore,
    FirstPartyCandidateStore,
    FirstPartyCaptureRegistry,
)


class FirstPartyCaptureError(ValueError):
    """Raised when Stage 4G candidate capture fails closed."""


FORBIDDEN_INPUT_FIELDS = frozenset(
    {
        "name",
        "full_name",
        "first_name",
        "last_name",
        "email",
        "email_address",
        "phone",
        "phone_number",
        "mobile",
        "address",
        "street_address",
        "postcode",
        "postal_code",
        "ip_address",
        "device_id",
        "cookie",
        "raw_response",
        "full_transcript",
        "recording",
    }
)
PLACEHOLDER_MARKERS = (
    "placeholder",
    "replace_with",
    "replace with",
    "manual_test",
    "dummy",
    "sample answer",
    "lorem ipsum",
)
EMAIL_PATTERN = re.compile(
    r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b",
    re.IGNORECASE,
)
PHONE_PATTERN = re.compile(
    r"(?<!\d)(?:\+?\d[\s().-]*){10,15}(?!\d)"
)
TOKEN_PATTERN = re.compile(r"^[A-Za-z0-9_.:-]{3,120}$")


class FirstPartyCaptureService:
    """Validate a batch and append only sanitized candidates."""

    POLICY_VERSION = "STAGE4G-0.1"
    POLICY_ROOT = Path("config")
    REPORT_ROOT = Path("reports/research/first_party_capture")

    def __init__(
        self,
        *,
        candidate_store: FirstPartyCandidateStore | None = None,
        capture_registry: FirstPartyCaptureRegistry | None = None,
    ) -> None:
        self.project_root = Path.cwd().resolve()
        self.policy_root = (
            self.project_root / self.POLICY_ROOT
        ).resolve()
        self.report_root = (
            self.project_root / self.REPORT_ROOT
        ).resolve()
        self.candidate_store = (
            candidate_store or FirstPartyCandidateStore()
        )
        self.capture_registry = (
            capture_registry or FirstPartyCaptureRegistry()
        )

    def capture(
        self,
        *,
        input_file: str | Path,
        policy_file: str | Path,
        output_file: str | Path,
    ) -> dict[str, Any]:
        input_path = Path(input_file).resolve()
        if not input_path.is_file():
            raise FirstPartyCaptureError(
                f"Submission input does not exist: {input_file}"
            )
        policy_path = self._controlled_file(
            Path(policy_file),
            root=self.policy_root,
            suffix=".json",
            label="campaign policy",
        )
        output_path = self._controlled_output(
            Path(output_file),
            root=self.report_root,
            suffix=".json",
            label="capture report",
        )
        if output_path.exists():
            raise FirstPartyCaptureError(
                "Capture report already exists and will not be overwritten"
            )

        policy = self._load_object(policy_path)
        submissions = self._load_submissions(input_path)
        campaign_id = self._required_text(
            "campaign_id",
            policy.get("campaign_id", ""),
        )
        policy_id = self._required_text(
            "policy_id",
            policy.get("policy_id", ""),
        )
        input_hash = self._file_hash(input_path)
        policy_hash = self._file_hash(policy_path)
        batch_id = self._batch_id(
            campaign_id,
            input_hash,
            policy_hash,
        )
        if self.capture_registry.has_batch(batch_id):
            raise FirstPartyCaptureError(
                "This capture batch has already been processed"
            )

        candidate_path = self.candidate_store.path_for(campaign_id)
        existing = self.candidate_store.read(candidate_path)
        submission_ids = {
            str(record.get("submission_id", ""))
            for record in existing
        }
        fingerprints = {
            str(record.get("response_fingerprint", ""))
            for record in existing
        }
        source_references = {
            str(record.get("source_reference", ""))
            for record in existing
        }

        accepted: list[dict[str, Any]] = []
        blocked: list[dict[str, Any]] = []
        for index, raw in enumerate(submissions, start=1):
            candidate, reasons = self._candidate(
                raw=raw,
                index=index,
                policy=policy,
                policy_hash=policy_hash,
            )
            if candidate is not None:
                if candidate["submission_id"] in submission_ids:
                    reasons.append("duplicate_submission_id")
                if candidate["response_fingerprint"] in fingerprints:
                    reasons.append("duplicate_response_fingerprint")
                if candidate["source_reference"] in source_references:
                    reasons.append("duplicate_source_reference")

            reasons = list(dict.fromkeys(reasons))
            if candidate is None or reasons:
                blocked.append(
                    {
                        "input_index": index,
                        "submission_id": (
                            str(raw.get("submission_id", ""))
                            if isinstance(raw, dict)
                            else ""
                        ),
                        "blocking_reasons": reasons
                        or ["submission_not_an_object"],
                    }
                )
                continue

            accepted.append(candidate)
            submission_ids.add(candidate["submission_id"])
            fingerprints.add(candidate["response_fingerprint"])
            source_references.add(candidate["source_reference"])

        candidate_snapshot = ControlledJsonlStore.snapshot(
            candidate_path
        )
        registry_snapshot = ControlledJsonlStore.snapshot(
            self.capture_registry.registry_path
        )
        try:
            self.candidate_store.append_many(
                candidate_path,
                accepted,
            )
            report = {
                "batch_id": batch_id,
                "campaign_id": campaign_id,
                "policy_id": policy_id,
                "policy_path": self._project_path(policy_path),
                "policy_hash": policy_hash,
                "input_path": self._project_path(input_path),
                "input_hash": input_hash,
                "candidate_path": self._project_path(candidate_path),
                "received": len(submissions),
                "accepted": len(accepted),
                "blocked": len(blocked),
                "blocked_submissions": blocked,
                "captured_at": datetime.now(UTC).isoformat(),
                "protected_actions": {
                    "validation_evidence_log_modified": False,
                    "theme_state_modified": False,
                    "public_action_taken": False,
                    "automatic_outreach": False,
                },
            }
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(
                json.dumps(report, indent=2, ensure_ascii=False)
                + "\n",
                encoding="utf-8",
            )
            self.capture_registry.append_many(
                self.capture_registry.registry_path,
                [
                    {
                        "batch_id": batch_id,
                        "campaign_id": campaign_id,
                        "accepted": len(accepted),
                        "blocked": len(blocked),
                        "candidate_path": self._project_path(
                            candidate_path
                        ),
                        "report_path": self._project_path(output_path),
                        "captured_at": report["captured_at"],
                    }
                ],
            )
            return report
        except Exception:
            ControlledJsonlStore.restore(
                candidate_path,
                candidate_snapshot,
            )
            ControlledJsonlStore.restore(
                self.capture_registry.registry_path,
                registry_snapshot,
            )
            if output_path.exists():
                output_path.unlink()
            raise

    def _candidate(
        self,
        *,
        raw: Any,
        index: int,
        policy: dict[str, Any],
        policy_hash: str,
    ) -> tuple[dict[str, Any] | None, list[str]]:
        if not isinstance(raw, dict):
            return None, ["submission_not_an_object"]
        reasons: list[str] = []
        forbidden = sorted(
            str(key)
            for key in raw
            if str(key).strip().lower() in FORBIDDEN_INPUT_FIELDS
        )
        if forbidden:
            reasons.append(
                "forbidden_fields:" + ",".join(forbidden)
            )

        values = {
            "campaign_id": str(raw.get("campaign_id", "")).strip(),
            "submission_id": str(raw.get("submission_id", "")).strip(),
            "participant_token": str(
                raw.get("participant_token", "")
            ).strip(),
            "participant_role": str(
                raw.get("participant_role", "")
            ).strip().lower(),
            "capture_method": str(
                raw.get("capture_method", "")
            ).strip().lower(),
            "evidence_kind": str(
                raw.get("evidence_kind", "")
            ).strip().lower(),
            "attestation_basis": str(
                raw.get("attestation_basis", "")
            ).strip().lower(),
            "evidence_summary": " ".join(
                str(raw.get("evidence_summary", "")).split()
            ),
            "source_reference": str(
                raw.get("source_reference", "")
            ).strip(),
            "consent_version": str(
                raw.get("consent_version", "")
            ).strip(),
            "question_set_version": str(
                raw.get("question_set_version", "")
            ).strip(),
            "signal_strength": str(
                raw.get("signal_strength", "")
            ).strip().lower(),
        }
        required = (
            "campaign_id",
            "submission_id",
            "participant_role",
            "capture_method",
            "evidence_kind",
            "attestation_basis",
            "evidence_summary",
            "source_reference",
            "question_set_version",
            "signal_strength",
        )
        for field_name in required:
            if not values[field_name]:
                reasons.append(f"{field_name}_missing")

        if values["campaign_id"] != str(
            policy.get("campaign_id", "")
        ):
            reasons.append("campaign_id_mismatch")
        for field_name in (
            "submission_id",
            "source_reference",
        ):
            value = values[field_name]
            if value and not TOKEN_PATTERN.fullmatch(value):
                reasons.append(f"{field_name}_invalid")
        participant_token = values["participant_token"]
        if participant_token and not TOKEN_PATTERN.fullmatch(
            participant_token
        ):
            reasons.append("participant_token_invalid")

        summary = values["evidence_summary"]
        if len(summary) < 30:
            reasons.append("evidence_summary_too_short")
        if len(summary) > 1_200:
            reasons.append("evidence_summary_too_long")
        if EMAIL_PATTERN.search(summary):
            reasons.append("email_detected_in_summary")
        if PHONE_PATTERN.search(summary):
            reasons.append("phone_detected_in_summary")
        if any(
            marker in summary.lower()
            for marker in PLACEHOLDER_MARKERS
        ):
            reasons.append("placeholder_or_synthetic_marker")
        if bool(raw.get("self_submission", False)):
            reasons.append("self_submission_not_allowed")
        if bool(raw.get("synthetic_submission", False)):
            reasons.append("synthetic_submission_not_allowed")

        allowed_roles = {
            str(value).lower()
            for value in policy.get(
                "allowed_participant_roles",
                [],
            )
        }
        if values["participant_role"] not in allowed_roles:
            reasons.append("participant_role_not_allowed")

        rules = policy.get("evidence_rules")
        rule = (
            rules.get(values["evidence_kind"])
            if isinstance(rules, dict)
            else None
        )
        if not isinstance(rule, dict):
            reasons.append("evidence_kind_not_allowed")
            rule = {}

        if values["capture_method"] not in {
            str(value).lower()
            for value in rule.get(
                "allowed_capture_methods",
                [],
            )
        }:
            reasons.append("capture_method_not_allowed")
        if values["attestation_basis"] not in {
            str(value).lower()
            for value in rule.get(
                "allowed_attestation_bases",
                [],
            )
        }:
            reasons.append("attestation_basis_not_allowed")

        requires_consent = bool(
            rule.get("requires_consent", True)
        )
        if requires_consent:
            if raw.get("consent_to_research") is not True:
                reasons.append("research_consent_required")
            if values["consent_version"] != str(
                policy.get("consent_version", "")
            ):
                reasons.append("consent_version_mismatch")
        if (
            bool(rule.get("requires_participant_token", True))
            and not participant_token
        ):
            reasons.append("participant_token_missing")
        if (
            bool(rule.get("requires_confirmed_action", False))
            and raw.get("action_confirmed") is not True
        ):
            reasons.append("confirmed_action_required")
        if bool(rule.get("requires_measurement", False)):
            count = raw.get("measurement_count")
            if (
                not isinstance(count, int)
                or isinstance(count, bool)
                or count < 0
            ):
                reasons.append("valid_measurement_count_required")
            if not str(
                raw.get("measurement_window", "")
            ).strip():
                reasons.append("measurement_window_required")

        if values["signal_strength"] not in {
            "strong",
            "medium",
            "weak",
            "negative",
        }:
            reasons.append("signal_strength_invalid")
        if not isinstance(raw.get("supports_validation"), bool):
            reasons.append("supports_validation_not_boolean")

        evidence_type = str(
            rule.get("evidence_type", "")
        ).strip().lower()
        review_mode = str(
            rule.get("review_mode", "")
        ).strip().lower()
        if review_mode == "importable":
            if evidence_type not in (
                ValidationEvidenceLog
                .HUMAN_FIRST_PARTY_EVIDENCE_TYPES
            ):
                reasons.append(
                    "evidence_type_not_allowed_for_first_party"
                )
        elif review_mode == "hold_only":
            if evidence_type:
                reasons.append(
                    "hold_only_record_must_not_set_evidence_type"
                )
        else:
            reasons.append("policy_review_mode_invalid")

        if reasons:
            return None, reasons

        candidate = {
            "schema_version": self.POLICY_VERSION,
            "campaign_id": values["campaign_id"],
            "policy_id": str(policy.get("policy_id", "")),
            "policy_hash": policy_hash,
            "submission_id": values["submission_id"],
            "captured_at": self._iso_datetime(
                raw.get("captured_at", "")
            ),
            "capture_method": values["capture_method"],
            "evidence_kind": values["evidence_kind"],
            "evidence_type": evidence_type,
            "review_mode": review_mode,
            "participant_token": participant_token,
            "participant_role": values["participant_role"],
            "attestation_basis": values["attestation_basis"],
            "evidence_summary": summary,
            "signal_strength": values["signal_strength"],
            "supports_validation": bool(
                raw.get("supports_validation")
            ),
            "source_reference": values["source_reference"],
            "consent_to_research": bool(
                raw.get("consent_to_research", False)
            ),
            "consent_version": values["consent_version"],
            "question_set_version": values[
                "question_set_version"
            ],
            "action_confirmed": bool(
                raw.get("action_confirmed", False)
            ),
            "measurement_count": raw.get("measurement_count"),
            "measurement_window": str(
                raw.get("measurement_window", "")
            ).strip(),
            "received_at": datetime.now(UTC).isoformat(),
            "input_index": index,
        }
        candidate["response_fingerprint"] = self._payload_hash(
            {
                "campaign_id": candidate["campaign_id"],
                "participant_token": participant_token,
                "evidence_kind": candidate["evidence_kind"],
                "evidence_summary": summary.lower(),
            }
        )
        candidate["candidate_hash"] = self._payload_hash(candidate)
        return candidate, []

    @staticmethod
    def _load_submissions(path: Path) -> list[Any]:
        if path.suffix == ".jsonl":
            records: list[Any] = []
            for line_number, line in enumerate(
                path.read_text(encoding="utf-8").splitlines(),
                start=1,
            ):
                if not line.strip():
                    continue
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError as exc:
                    raise FirstPartyCaptureError(
                        "Submission JSONL is invalid at line "
                        f"{line_number}"
                    ) from exc
            return records
        if path.suffix != ".json":
            raise FirstPartyCaptureError(
                "Submission input must be .json or .jsonl"
            )
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise FirstPartyCaptureError(
                "Submission JSON is invalid"
            ) from exc
        if isinstance(payload, list):
            return payload
        if isinstance(payload, dict):
            submissions = payload.get("submissions")
            return submissions if isinstance(submissions, list) else [payload]
        raise FirstPartyCaptureError(
            "Submission JSON must be an object or list"
        )

    @staticmethod
    def _load_object(path: Path) -> dict[str, Any]:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise FirstPartyCaptureError(
                f"Could not read JSON object: {path}"
            ) from exc
        if not isinstance(payload, dict):
            raise FirstPartyCaptureError(
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
            raise FirstPartyCaptureError(
                f"{label} must stay inside {self._project_path(root)}"
            )
        if resolved.suffix != suffix or not resolved.is_file():
            raise FirstPartyCaptureError(
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
            raise FirstPartyCaptureError(
                f"{label} must stay inside {self._project_path(root)}"
            )
        if resolved.suffix != suffix:
            raise FirstPartyCaptureError(
                f"{label} must use {suffix}"
            )
        return resolved

    def _project_path(self, path: Path) -> str:
        try:
            return str(path.resolve().relative_to(self.project_root))
        except ValueError as exc:
            raise FirstPartyCaptureError(
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
            raise FirstPartyCaptureError(
                f"{field_name} is required"
            )
        return " ".join(value.split())

    @staticmethod
    def _iso_datetime(value: Any) -> str:
        if not isinstance(value, str) or not value.strip():
            raise FirstPartyCaptureError(
                "captured_at is required"
            )
        normalized = value.strip().replace("Z", "+00:00")
        try:
            parsed = datetime.fromisoformat(normalized)
        except ValueError as exc:
            raise FirstPartyCaptureError(
                "captured_at must be ISO-8601"
            ) from exc
        if parsed.tzinfo is None:
            raise FirstPartyCaptureError(
                "captured_at must include a timezone"
            )
        return parsed.astimezone(UTC).isoformat()

    @staticmethod
    def _payload_hash(payload: dict[str, Any]) -> str:
        encoded = json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode()
        return hashlib.sha256(encoded).hexdigest()

    @staticmethod
    def _file_hash(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(65_536), b""):
                digest.update(chunk)
        return digest.hexdigest()

    @staticmethod
    def _batch_id(
        campaign_id: str,
        input_hash: str,
        policy_hash: str,
    ) -> str:
        material = (
            f"{campaign_id}|{input_hash}|{policy_hash}"
        ).encode()
        return "FPCB-" + hashlib.sha256(material).hexdigest()[:20]
