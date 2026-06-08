import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

from src.utils.path_normalizer import PathNormalizerError, ProjectPathNormalizer


class ValidationEvidenceLogError(Exception):
    pass


@dataclass(frozen=True)
class ValidationEvidenceEntry:
    theme: str
    validation_plan_path: str
    evidence_type: str
    evidence_summary: str
    source_reference: str
    signal_strength: str
    supports_validation: bool
    timestamp: str
    notes: str = ""


class ValidationEvidenceLog:
    """
    Stores validation evidence for a validation plan.

    Purpose:
    - record interviews, waitlist signals, competitor checks, landing page results, and risk findings
    - keep validation evidence traceable before any build planning
    - prevent VALIDATION_READY from becoming BUILD_NOW without evidence

    Security:
    - writes only inside reports/intelligence
    - stores metadata and summaries only
    - does not approve building
    """

    DEFAULT_LOG_PATH = Path("reports/intelligence/validation_evidence_log.json")

    ALLOWED_EVIDENCE_TYPES = {
        "customer_interview",
        "landing_page_result",
        "waitlist_signup",
        "competitor_check",
        "willingness_to_pay",
        "risk_finding",
        "manual_research",
    }

    ALLOWED_SIGNAL_STRENGTHS = {
        "strong",
        "medium",
        "weak",
        "negative",
    }

    def __init__(self, log_path: str | Path = DEFAULT_LOG_PATH):
        self.log_path = self._validate_log_path(Path(log_path))
        self.path_normalizer = ProjectPathNormalizer()
        self.log_path.parent.mkdir(parents=True, exist_ok=True)

    def add_entry(
        self,
        *,
        theme: str,
        validation_plan_path: str,
        evidence_type: str,
        evidence_summary: str,
        source_reference: str,
        signal_strength: str,
        supports_validation: bool,
        notes: str = "",
    ) -> ValidationEvidenceEntry:
        evidence_type = evidence_type.strip().lower()
        signal_strength = signal_strength.strip().lower()

        if evidence_type not in self.ALLOWED_EVIDENCE_TYPES:
            raise ValidationEvidenceLogError(
                f"Unsupported evidence type: {evidence_type}"
            )

        if signal_strength not in self.ALLOWED_SIGNAL_STRENGTHS:
            raise ValidationEvidenceLogError(
                f"Unsupported signal strength: {signal_strength}"
            )

        if not theme.strip():
            raise ValidationEvidenceLogError("Evidence entry requires a theme")

        if not evidence_summary.strip():
            raise ValidationEvidenceLogError("Evidence entry requires a summary")

        if not source_reference.strip():
            raise ValidationEvidenceLogError("Evidence entry requires a source reference")

        entry = ValidationEvidenceEntry(
            theme=theme.strip(),
            validation_plan_path=self._normalize_validation_plan_path(
                validation_plan_path
            ),
            evidence_type=evidence_type,
            evidence_summary=evidence_summary.strip(),
            source_reference=source_reference.strip(),
            signal_strength=signal_strength,
            supports_validation=bool(supports_validation),
            timestamp=datetime.now(UTC).isoformat(),
            notes=notes.strip(),
        )

        data = self._load_log()
        data["evidence"].append(asdict(entry))
        self._write_log(data)

        return entry

    def list_entries(self) -> list[ValidationEvidenceEntry]:
        data = self._load_log()

        return [
            ValidationEvidenceEntry(
                theme=str(item["theme"]),
                validation_plan_path=str(item["validation_plan_path"]),
                evidence_type=str(item["evidence_type"]),
                evidence_summary=str(item["evidence_summary"]),
                source_reference=str(item["source_reference"]),
                signal_strength=str(item["signal_strength"]),
                supports_validation=bool(item["supports_validation"]),
                timestamp=str(item["timestamp"]),
                notes=str(item.get("notes", "")),
            )
            for item in data["evidence"]
        ]

    def list_entries_for_theme(self, theme: str) -> list[ValidationEvidenceEntry]:
        expected = theme.strip().lower()

        return [
            entry for entry in self.list_entries()
            if entry.theme.lower() == expected
        ]

    def _load_log(self) -> dict:
        if not self.log_path.exists():
            return {"evidence": []}

        try:
            data = json.loads(self.log_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ValidationEvidenceLogError(
                "Validation evidence log contains invalid JSON"
            ) from exc

        if not isinstance(data, dict):
            raise ValidationEvidenceLogError(
                "Validation evidence log must contain a JSON object"
            )

        if "evidence" not in data:
            data["evidence"] = []

        if not isinstance(data["evidence"], list):
            raise ValidationEvidenceLogError(
                "Validation evidence log 'evidence' field must be a list"
            )

        return data

    def _write_log(self, data: dict) -> None:
        self.log_path.write_text(
            json.dumps(data, indent=2, sort_keys=True),
            encoding="utf-8",
        )

    def _normalize_validation_plan_path(self, validation_plan_path: str) -> str:
        try:
            return self.path_normalizer.normalize(validation_plan_path)
        except PathNormalizerError as exc:
            raise ValidationEvidenceLogError(
                "Validation plan path is unsafe"
            ) from exc

    def _validate_log_path(self, log_path: Path) -> Path:
        resolved = log_path.resolve()
        project_root = Path.cwd().resolve()
        allowed_root = (project_root / "reports" / "intelligence").resolve()

        if not str(resolved).startswith(str(allowed_root)):
            raise ValidationEvidenceLogError(
                "Validation evidence log must stay inside reports/intelligence"
            )

        if resolved.suffix != ".json":
            raise ValidationEvidenceLogError(
                "Validation evidence log must be a JSON file"
            )

        return resolved
