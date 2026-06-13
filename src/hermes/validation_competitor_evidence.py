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
    Logs competitor-check findings into the validation evidence log.

    Purpose:
    - record agent/user competitor research as secondary evidence
    - clearly separate competitor evidence from customer interviews
    - support both validating and weakening findings
    - avoid treating competitor research as direct customer proof

    This does not approve human review or build planning.
    """

    def __init__(self, evidence_log: ValidationEvidenceLog | None = None):
        self.evidence_log = evidence_log or ValidationEvidenceLog()

    def log_competitor_evidence(
        self,
        evidence: CompetitorEvidenceInput,
    ) -> ValidationEvidenceEntry:
        self._validate_input(evidence)

        summary = (
            f"Competitor: {evidence.competitor_name}. "
            f"Finding: {evidence.finding_summary}"
        )

        notes = self._build_notes(evidence)

        try:
            return self.evidence_log.add_entry(
                theme=evidence.theme,
                validation_plan_path=evidence.validation_plan_path,
                evidence_type="competitor_check",
                evidence_summary=summary,
                source_reference=evidence.source_reference,
                signal_strength=evidence.signal_strength,
                supports_validation=evidence.supports_validation,
                notes=notes,
            )
        except ValidationEvidenceLogError as exc:
            raise ValidationCompetitorEvidenceError(
                "Could not log competitor evidence"
            ) from exc

    def _validate_input(self, evidence: CompetitorEvidenceInput) -> None:
        if not evidence.theme.strip():
            raise ValidationCompetitorEvidenceError("Theme is required")

        if not evidence.validation_plan_path.strip():
            raise ValidationCompetitorEvidenceError("Validation plan path is required")

        if not evidence.competitor_name.strip():
            raise ValidationCompetitorEvidenceError("Competitor name is required")

        if not evidence.finding_summary.strip():
            raise ValidationCompetitorEvidenceError("Finding summary is required")

        if not evidence.source_reference.strip():
            raise ValidationCompetitorEvidenceError("Source reference is required")

    def _build_notes(self, evidence: CompetitorEvidenceInput) -> str:
        base_note = (
            "Secondary competitor-check evidence. "
            "Do not treat as direct customer validation."
        )

        if evidence.notes.strip():
            return f"{base_note} {evidence.notes.strip()}"

        return base_note
