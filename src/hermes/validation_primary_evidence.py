from dataclasses import dataclass

from src.hermes.validation_evidence_log import (
    ValidationEvidenceEntry,
    ValidationEvidenceLog,
    ValidationEvidenceLogError,
)


class ValidationPrimaryEvidenceError(Exception):
    pass


@dataclass(frozen=True)
class PrimaryEvidenceInput:
    theme: str
    validation_plan_path: str
    evidence_type: str
    participant_reference: str
    finding_summary: str
    source_reference: str
    signal_strength: str
    supports_validation: bool
    notes: str = ""


class ValidationPrimaryEvidenceLogger:
    """
    Logs primary validation evidence into the validation evidence log.

    Purpose:
    - record direct customer or behavioural validation evidence
    - separate primary validation evidence from competitor/research evidence
    - prevent secondary evidence from being treated as customer proof

    This does not approve human review or building.
    """

    PRIMARY_EVIDENCE_TYPES = {
        "customer_interview",
        "willingness_to_pay",
        "landing_page_result",
        "waitlist_signup",
    }

    def __init__(self, evidence_log: ValidationEvidenceLog | None = None):
        self.evidence_log = evidence_log or ValidationEvidenceLog()

    def log_primary_evidence(
        self,
        evidence: PrimaryEvidenceInput,
    ) -> ValidationEvidenceEntry:
        self._validate_input(evidence)

        evidence_type = evidence.evidence_type.strip().lower()

        summary = (
            f"Participant/Signal: {evidence.participant_reference}. "
            f"Finding: {evidence.finding_summary}"
        )

        notes = self._build_notes(evidence)

        try:
            return self.evidence_log.add_entry(
                theme=evidence.theme,
                validation_plan_path=evidence.validation_plan_path,
                evidence_type=evidence_type,
                evidence_summary=summary,
                source_reference=evidence.source_reference,
                signal_strength=evidence.signal_strength,
                supports_validation=evidence.supports_validation,
                notes=notes,
            )
        except ValidationEvidenceLogError as exc:
            raise ValidationPrimaryEvidenceError(
                "Could not log primary validation evidence"
            ) from exc

    def _validate_input(self, evidence: PrimaryEvidenceInput) -> None:
        evidence_type = evidence.evidence_type.strip().lower()

        if evidence_type not in self.PRIMARY_EVIDENCE_TYPES:
            raise ValidationPrimaryEvidenceError(
                f"Unsupported primary evidence type: {evidence.evidence_type}"
            )

        if not evidence.theme.strip():
            raise ValidationPrimaryEvidenceError("Theme is required")

        if not evidence.validation_plan_path.strip():
            raise ValidationPrimaryEvidenceError("Validation plan path is required")

        if not evidence.participant_reference.strip():
            raise ValidationPrimaryEvidenceError("Participant reference is required")

        if not evidence.finding_summary.strip():
            raise ValidationPrimaryEvidenceError("Finding summary is required")

        if not evidence.source_reference.strip():
            raise ValidationPrimaryEvidenceError("Source reference is required")

    def _build_notes(self, evidence: PrimaryEvidenceInput) -> str:
        base_note = (
            "Primary validation evidence. "
            "Treat as direct customer or behavioural validation signal."
        )

        if evidence.notes.strip():
            return f"{base_note} {evidence.notes.strip()}"

        return base_note
