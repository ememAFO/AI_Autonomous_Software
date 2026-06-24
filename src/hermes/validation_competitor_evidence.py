from dataclasses import dataclass

from src.hermes.validation_evidence_log import (
    ValidationEvidenceEntry,
    ValidationEvidenceLog,
    ValidationEvidenceLogError,
)


class ValidationCompetitorEvidenceError(Exception):
    pass


@dataclass(frozen=True)
class CompetitorEvidenceInput:
    theme: str
    validation_plan_path: str
    competitor_name: str
    finding_summary: str
    source_reference: str
    signal_strength: str
    supports_validation: bool
    notes: str = ""


class ValidationCompetitorEvidenceLogger:
    """
    Logs public competitor research as secondary evidence.

    Competitor research can support or weaken a theme, but it never counts as
    first-party customer validation.
    """

    def __init__(self, evidence_log: ValidationEvidenceLog | None = None):
        self.evidence_log = evidence_log or ValidationEvidenceLog()

    def log_competitor_evidence(
        self,
        evidence: CompetitorEvidenceInput,
    ) -> ValidationEvidenceEntry:
        self._validate_input(evidence)

        summary = (
            f"Competitor: {evidence.competitor_name.strip()}. "
            f"Finding: {evidence.finding_summary.strip()}"
        )

        try:
            return self.evidence_log.add_entry(
                theme=evidence.theme,
                validation_plan_path=evidence.validation_plan_path,
                evidence_type="competitor_check",
                evidence_summary=summary,
                source_reference=evidence.source_reference,
                signal_strength=evidence.signal_strength,
                supports_validation=evidence.supports_validation,
                source_trust=ValidationEvidenceLog.PUBLIC_COMPETITOR,
                notes=self._build_notes(evidence),
            )
        except ValidationEvidenceLogError as exc:
            raise ValidationCompetitorEvidenceError(
                "Could not log competitor evidence"
            ) from exc

    def _validate_input(self, evidence: CompetitorEvidenceInput) -> None:
        self._validate_required_text("theme", evidence.theme)
        self._validate_required_text(
            "validation_plan_path",
            evidence.validation_plan_path,
        )
        self._validate_required_text(
            "competitor_name",
            evidence.competitor_name,
        )
        self._validate_required_text(
            "finding_summary",
            evidence.finding_summary,
        )
        self._validate_required_text(
            "source_reference",
            evidence.source_reference,
        )

    @staticmethod
    def _validate_required_text(field_name: str, value: str) -> None:
        if not isinstance(value, str) or not value.strip():
            raise ValidationCompetitorEvidenceError(
                f"{field_name} is required"
            )

    def _build_notes(self, evidence: CompetitorEvidenceInput) -> str:
        base_note = (
            "Secondary competitor-check evidence. "
            "Source trust: public_competitor. "
            "Do not treat as direct customer "
            "validation."
        )

        if evidence.notes.strip():
            return f"{base_note} {evidence.notes.strip()}"

        return base_note
