from dataclasses import dataclass
from datetime import UTC, datetime

from src.hermes.theme_state_registry import (
    InvalidTransitionError,
    ThemeNotFoundError,
    ThemeStateRegistry,
    ThemeStateRegistryError,
)
from src.hermes.validation_evidence_summary import (
    ValidationEvidenceSummarizer,
    ValidationEvidenceSummary,
)


class ValidationGateError(Exception):
    pass


@dataclass(frozen=True)
class ValidationGateResult:
    theme_id: str
    theme_name: str
    current_state: str | None
    gate_status: str
    reason: str
    evidence_status: str
    recommended_next_action: str
    state_changed: bool
    new_state: str | None
    policy_version: str
    run_id: str
    timestamp: str


class ValidationGate:
    """
    Hard gate between validation evidence collection and human review.

    Purpose:
    - prevent themes from moving to READY_FOR_REVIEW without enough evidence
    - enforce state progression through ThemeStateRegistry
    - keep validation evidence assessment separate from build planning

    This gate does not approve building.
    It only allows VALIDATING -> READY_FOR_REVIEW.
    """

    REQUIRED_CURRENT_STATE = "VALIDATING"
    REQUIRED_EVIDENCE_STATUS = "READY_FOR_HUMAN_REVIEW"
    OUTPUT_STATE = "READY_FOR_REVIEW"

    def __init__(
        self,
        *,
        state_registry: ThemeStateRegistry | None = None,
        evidence_summarizer: ValidationEvidenceSummarizer | None = None,
    ):
        self.state_registry = state_registry or ThemeStateRegistry()
        self.evidence_summarizer = evidence_summarizer or ValidationEvidenceSummarizer()

    def evaluate(
        self,
        *,
        theme_id: str,
        theme_name: str,
        policy_version: str,
        run_id: str,
        related_artifact_id: str,
    ) -> ValidationGateResult:
        current_state = self.state_registry.get_current_state(theme_id)

        if current_state is None:
            raise ThemeNotFoundError(
                f"Theme must be registered before validation gate review: {theme_id}"
            )

        evidence_summary = self.evidence_summarizer.summarize_theme(theme_name)

        if current_state != self.REQUIRED_CURRENT_STATE:
            return self._blocked_result(
                theme_id=theme_id,
                theme_name=theme_name,
                current_state=current_state,
                evidence_summary=evidence_summary,
                reason=(
                    f"Validation gate requires current state "
                    f"{self.REQUIRED_CURRENT_STATE}, got {current_state}."
                ),
                policy_version=policy_version,
                run_id=run_id,
            )

        if evidence_summary.status != self.REQUIRED_EVIDENCE_STATUS:
            return self._blocked_result(
                theme_id=theme_id,
                theme_name=theme_name,
                current_state=current_state,
                evidence_summary=evidence_summary,
                reason=(
                    f"Validation evidence is not ready for human review: "
                    f"{evidence_summary.status}."
                ),
                policy_version=policy_version,
                run_id=run_id,
            )

        try:
            event = self.state_registry.transition(
                theme_id=theme_id,
                theme_name=theme_name,
                new_state=self.OUTPUT_STATE,
                trigger="validation_gate_passed",
                reason="Validation evidence met human review threshold.",
                changed_by="ValidationGate",
                related_artifact_id=related_artifact_id,
                policy_version=policy_version,
                run_id=run_id,
            )
        except ThemeStateRegistryError as exc:
            raise ValidationGateError(
                "Validation gate could not write state transition"
            ) from exc

        return ValidationGateResult(
            theme_id=theme_id,
            theme_name=theme_name,
            current_state=current_state,
            gate_status="READY_FOR_HUMAN_REVIEW",
            reason="Validation gate passed.",
            evidence_status=evidence_summary.status,
            recommended_next_action=(
                "Generate a human review request. This still does not approve building."
            ),
            state_changed=True,
            new_state=event.new_state,
            policy_version=policy_version,
            run_id=run_id,
            timestamp=datetime.now(UTC).isoformat(),
        )

    def _blocked_result(
        self,
        *,
        theme_id: str,
        theme_name: str,
        current_state: str | None,
        evidence_summary: ValidationEvidenceSummary,
        reason: str,
        policy_version: str,
        run_id: str,
    ) -> ValidationGateResult:
        return ValidationGateResult(
            theme_id=theme_id,
            theme_name=theme_name,
            current_state=current_state,
            gate_status="BLOCKED",
            reason=reason,
            evidence_status=evidence_summary.status,
            recommended_next_action=evidence_summary.recommended_next_action,
            state_changed=False,
            new_state=current_state,
            policy_version=policy_version,
            run_id=run_id,
            timestamp=datetime.now(UTC).isoformat(),
        )
