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
    source_trust: str = "legacy_unverified"


class ValidationEvidenceLog:
    """
    Stores traceable validation evidence for a validation plan.

    New records must declare their source-trust class. Missing source trust in
    older JSON records is retained as legacy_unverified history and excluded
    from gate-safe evidence counts.

    Security:
    - writes only inside reports/intelligence
    - stores metadata and summaries only
    - keeps raw source material outside the repository
    - does not approve building
    """

    DEFAULT_LOG_PATH = Path("reports/intelligence/validation_evidence_log.json")

    HUMAN_ATTESTED_FIRST_PARTY = "human_attested_first_party"
    PUBLIC_DATASET = "public_dataset"
    PUBLIC_COMPETITOR = "public_competitor"
    LEGACY_UNVERIFIED = "legacy_unverified"

    ALLOWED_SOURCE_TRUSTS = {
        HUMAN_ATTESTED_FIRST_PARTY,
        PUBLIC_DATASET,
        PUBLIC_COMPETITOR,
        LEGACY_UNVERIFIED,
    }

    ALLOWED_EVIDENCE_TYPES = {
        "customer_interview",
        "landing_page_result",
        "waitlist_signup",
        "competitor_check",
        "willingness_to_pay",
        "risk_finding",
        "manual_research",
    }

    PRIMARY_EVIDENCE_TYPES = {
        "customer_interview",
        "landing_page_result",
        "waitlist_signup",
        "willingness_to_pay",
    }

    PUBLIC_DATASET_EVIDENCE_TYPES = {
        "manual_research",
        "risk_finding",
    }

    PUBLIC_COMPETITOR_EVIDENCE_TYPES = {
        "competitor_check",
        "risk_finding",
    }

    HUMAN_FIRST_PARTY_EVIDENCE_TYPES = (
        PRIMARY_EVIDENCE_TYPES | {"risk_finding"}
    )

    ALLOWED_SIGNAL_STRENGTHS = {
        "strong",
        "medium",
        "weak",
        "negative",
    }

    def __init__(
        self,
        log_path: str | Path = DEFAULT_LOG_PATH,
    ):
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
        source_trust: str | None = None,
        notes: str = "",
    ) -> ValidationEvidenceEntry:
        evidence_type = self._normalize_evidence_type(evidence_type)
        signal_strength = self._normalize_signal_strength(signal_strength)
        source_trust = self._resolve_new_source_trust(source_trust)

        self._validate_required_text("theme", theme)
        self._validate_required_text("evidence_summary", evidence_summary)
        self._validate_required_text("source_reference", source_reference)
        self._validate_source_trust_for_evidence(
            evidence_type=evidence_type,
            source_trust=source_trust,
        )

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
            source_trust=source_trust,
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
                evidence_type=self._normalize_evidence_type(
                    str(item["evidence_type"])
                ),
                evidence_summary=str(item["evidence_summary"]),
                source_reference=str(item["source_reference"]),
                signal_strength=self._normalize_signal_strength(
                    str(item["signal_strength"])
                ),
                supports_validation=bool(item["supports_validation"]),
                timestamp=str(item["timestamp"]),
                notes=str(item.get("notes", "")),
                source_trust=self._normalize_source_trust(
                    item.get("source_trust", self.LEGACY_UNVERIFIED),
                    allow_legacy=True,
                ),
            )
            for item in data["evidence"]
        ]

    def list_entries_for_theme(self, theme: str) -> list[ValidationEvidenceEntry]:
        expected = self._validate_required_text("theme", theme).lower()

        return [
            entry
            for entry in self.list_entries()
            if entry.theme.lower() == expected
        ]

    def _resolve_new_source_trust(self, value: str | None) -> str:
        if value is None:
            raise ValidationEvidenceLogError(
                "New validation evidence requires source_trust"
            )

        return self._normalize_source_trust(
            value,
            allow_legacy=False,
        )

    def _validate_source_trust_for_evidence(
        self,
        *,
        evidence_type: str,
        source_trust: str,
    ) -> None:
        if source_trust == self.PUBLIC_DATASET:
            if evidence_type not in self.PUBLIC_DATASET_EVIDENCE_TYPES:
                raise ValidationEvidenceLogError(
                    "public_dataset evidence may only use manual_research "
                    "or risk_finding"
                )
            return

        if source_trust == self.PUBLIC_COMPETITOR:
            if evidence_type not in self.PUBLIC_COMPETITOR_EVIDENCE_TYPES:
                raise ValidationEvidenceLogError(
                    "public_competitor evidence may only use competitor_check "
                    "or risk_finding"
                )
            return

        if source_trust == self.HUMAN_ATTESTED_FIRST_PARTY:
            if evidence_type not in self.HUMAN_FIRST_PARTY_EVIDENCE_TYPES:
                raise ValidationEvidenceLogError(
                    "human_attested_first_party evidence must be direct "
                    "customer/behavioural evidence or a direct risk finding"
                )
            return

        raise ValidationEvidenceLogError(
            "legacy_unverified is reserved for historical records and "
            "cannot be used for new validation evidence"
        )

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

    def _normalize_evidence_type(self, value: str) -> str:
        evidence_type = self._validate_required_text(
            "evidence_type",
            value,
        ).lower()

        if evidence_type not in self.ALLOWED_EVIDENCE_TYPES:
            raise ValidationEvidenceLogError(
                f"Unsupported evidence type: {evidence_type}"
            )

        return evidence_type

    def _normalize_signal_strength(self, value: str) -> str:
        signal_strength = self._validate_required_text(
            "signal_strength",
            value,
        ).lower()

        if signal_strength not in self.ALLOWED_SIGNAL_STRENGTHS:
            raise ValidationEvidenceLogError(
                f"Unsupported signal strength: {signal_strength}"
            )

        return signal_strength

    def _normalize_source_trust(
        self,
        value: object,
        *,
        allow_legacy: bool,
    ) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ValidationEvidenceLogError("source_trust is required")

        source_trust = value.strip().lower()

        if source_trust not in self.ALLOWED_SOURCE_TRUSTS:
            raise ValidationEvidenceLogError(
                f"Unsupported source trust: {source_trust}"
            )

        if source_trust == self.LEGACY_UNVERIFIED and not allow_legacy:
            raise ValidationEvidenceLogError(
                "legacy_unverified cannot be used for new validation evidence"
            )

        return source_trust

    @staticmethod
    def _validate_required_text(field_name: str, value: object) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ValidationEvidenceLogError(
                f"Evidence entry requires {field_name}"
            )

        return value.strip()

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
        allowed_root = (
            project_root / "reports" / "intelligence"
        ).resolve()

        if not str(resolved).startswith(str(allowed_root)):
            raise ValidationEvidenceLogError(
                "Validation evidence log must stay inside reports/intelligence"
            )

        if resolved.suffix != ".json":
            raise ValidationEvidenceLogError(
                "Validation evidence log must be a JSON file"
            )

        return resolved
