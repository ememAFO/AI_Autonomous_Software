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
    Logs human-attested first-party evidence.

    The caller attests that the underlying interaction happened. This logger
    stores anonymised identifiers and summaries only; it does not store the
    participant's personal data or raw conversation.
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
            f"Participant/Signal: {evidence.participant_reference.strip()}. "
            f"Finding: {evidence.finding_summary.strip()}"
        )

        try:
            return self.evidence_log.add_entry(
                theme=evidence.theme,
                validation_plan_path=evidence.validation_plan_path,
                evidence_type=evidence_type,
                evidence_summary=summary,
                source_reference=evidence.source_reference,
                signal_strength=evidence.signal_strength,
                supports_validation=evidence.supports_validation,
                source_trust=(
                    ValidationEvidenceLog.HUMAN_ATTESTED_FIRST_PARTY
                ),
                notes=self._build_notes(evidence),
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

        self._validate_required_text("theme", evidence.theme)
        self._validate_required_text(
            "validation_plan_path",
            evidence.validation_plan_path,
        )
        self._validate_reference(
            "participant_reference",
            evidence.participant_reference,
        )
        self._validate_required_text(
            "finding_summary",
            evidence.finding_summary,
        )
        self._validate_reference("source_reference", evidence.source_reference)

    @staticmethod
    def _validate_required_text(field_name: str, value: str) -> None:
        if not isinstance(value, str) or not value.strip():
            raise ValidationPrimaryEvidenceError(f"{field_name} is required")

    @staticmethod
    def _validate_reference(field_name: str, value: str) -> None:
        if not isinstance(value, str) or not value.strip():
            raise ValidationPrimaryEvidenceError(f"{field_name} is required")

        if len(value.strip()) > 160:
            raise ValidationPrimaryEvidenceError(
                f"{field_name} must be 160 characters or fewer"
            )

    def _build_notes(self, evidence: PrimaryEvidenceInput) -> str:
        base_note = (
            "Primary validation evidence. "
            "Source trust: human_attested_first_party. "
            "Human-attested direct customer or behavioural evidence. "
            "Do not store personal data or raw conversations in this log."
        )

        if evidence.notes.strip():
            return f"{base_note} {evidence.notes.strip()}"

        return base_note
