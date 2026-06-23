from dataclasses import dataclass
from pathlib import Path

from src.hermes.theme_state_registry import (
    InvalidTransitionError,
    ThemeNotFoundError,
    ThemeStateRegistry,
    ThemeStateRegistryError,
)
from src.hermes.validation_evidence_summary import (
    ValidationEvidenceSummarizer,
)
from src.utils.path_normalizer import PathNormalizerError, ProjectPathNormalizer


class HumanReviewDecisionError(Exception):
    pass


@dataclass(frozen=True)
class HumanReviewReturnResult:
    theme_id: str
    theme_name: str
    previous_state: str
    new_state: str
    decision_status: str
    evidence_status: str
    reviewer_reference: str
    decision_reason: str
    review_context_path: str
    state_event_id: str
    policy_version: str
    run_id: str
    timestamp: str
    recommended_next_action: str


class HumanReviewDecisionService:
    """
    Records a human decision to reopen a review-ready theme for validation.

    This service exists for evidence repair after a prior validation gate event.
    It does not approve MVP planning or create a build state.
    """

    REQUIRED_CURRENT_STATE = "READY_FOR_REVIEW"
    REQUIRED_GATE_TRIGGER = "validation_gate_passed"
    REQUIRED_GATE_ACTOR = "ValidationGate"
    RETURN_STATUS = "RETURNED_TO_VALIDATION"

    def __init__(
        self,
        *,
        state_registry: ThemeStateRegistry | None = None,
        evidence_summarizer: ValidationEvidenceSummarizer | None = None,
    ):
        self.state_registry = state_registry or ThemeStateRegistry()
        self.evidence_summarizer = (
            evidence_summarizer or ValidationEvidenceSummarizer()
        )
        self.project_root = Path.cwd().resolve()
        self.intelligence_root = (
            self.project_root / "reports" / "intelligence"
        ).resolve()
        self.path_normalizer = ProjectPathNormalizer()

    def return_to_validation(
        self,
        *,
        theme_id: str,
        theme_name: str,
        reviewer_reference: str,
        decision_reason: str,
        review_context_path: str,
        policy_version: str,
        run_id: str,
    ) -> HumanReviewReturnResult:
        theme_id = self._validate_required_text("theme_id", theme_id)
        theme_name = self._validate_required_text("theme_name", theme_name)
        reviewer_reference = self._validate_reviewer_reference(
            reviewer_reference
        )
        decision_reason = self._validate_decision_reason(decision_reason)
        policy_version = self._validate_required_text(
            "policy_version",
            policy_version,
        )
        run_id = self._validate_required_text("run_id", run_id)

        try:
            self.state_registry.verify_integrity()
            events = self.state_registry.list_events_for_theme(theme_id)
        except ThemeStateRegistryError as exc:
            raise HumanReviewDecisionError(
                "Theme state registry integrity could not be verified"
            ) from exc

        if not events:
            raise HumanReviewDecisionError(
                f"Theme is not registered in the state registry: {theme_id}"
            )

        latest_event = events[-1]

        if latest_event.theme_name != theme_name:
            raise HumanReviewDecisionError(
                "Theme name does not match the registered state history"
            )

        if latest_event.new_state != self.REQUIRED_CURRENT_STATE:
            raise HumanReviewDecisionError(
                "Human review return requires current state "
                f"{self.REQUIRED_CURRENT_STATE}, got {latest_event.new_state}"
            )

        if latest_event.trigger != self.REQUIRED_GATE_TRIGGER:
            raise HumanReviewDecisionError(
                "READY_FOR_REVIEW must have been created by validation_gate_passed"
            )

        if latest_event.changed_by != self.REQUIRED_GATE_ACTOR:
            raise HumanReviewDecisionError(
                "READY_FOR_REVIEW must have been recorded by ValidationGate"
            )

        evidence_summary = self.evidence_summarizer.summarize_theme(theme_name)

        if evidence_summary.status == "READY_FOR_HUMAN_REVIEW":
            raise HumanReviewDecisionError(
                "Human review return is only available when current evidence "
                "requires repair or further validation"
            )

        normalized_context_path = self._resolve_review_context_path(
            review_context_path
        )

        state_reason = (
            "Human review returned this theme to validation. "
            f"Reviewer Reference: {reviewer_reference}. "
            f"Decision Reason: {decision_reason}. "
            f"Current Evidence Status: {evidence_summary.status}."
        )

        try:
            event = self.state_registry.return_to_validation_after_human_review(
                theme_id=theme_id,
                theme_name=theme_name,
                reason=state_reason,
                related_artifact_id=normalized_context_path,
                policy_version=policy_version,
                run_id=run_id,
            )
        except (
            InvalidTransitionError,
            ThemeNotFoundError,
            ThemeStateRegistryError,
        ) as exc:
            raise HumanReviewDecisionError(
                "Human review return could not record the state transition"
            ) from exc

        return HumanReviewReturnResult(
            theme_id=theme_id,
            theme_name=theme_name,
            previous_state=event.previous_state or "",
            new_state=event.new_state,
            decision_status=self.RETURN_STATUS,
            evidence_status=evidence_summary.status,
            reviewer_reference=reviewer_reference,
            decision_reason=decision_reason,
            review_context_path=normalized_context_path,
            state_event_id=event.event_id,
            policy_version=policy_version,
            run_id=run_id,
            timestamp=event.timestamp,
            recommended_next_action=(
                "Replace or verify weak evidence, collect contradictory or risk "
                "signals, then re-run the validation gate only when the current "
                "evidence is genuinely ready for review."
            ),
        )

    def _resolve_review_context_path(self, value: str) -> str:
        value = self._validate_required_text("review_context_path", value)
        candidate = Path(value)

        if candidate.is_absolute():
            resolved = candidate.resolve()
        else:
            resolved = (self.project_root / candidate).resolve()

        if not self._is_within(resolved, self.intelligence_root):
            raise HumanReviewDecisionError(
                "Review context must stay inside reports/intelligence"
            )

        if resolved.suffix != ".md":
            raise HumanReviewDecisionError(
                "Review context must be a Markdown file"
            )

        if not resolved.is_file():
            raise HumanReviewDecisionError(
                "Review context Markdown file does not exist"
            )

        try:
            return self.path_normalizer.normalize(str(resolved))
        except PathNormalizerError as exc:
            raise HumanReviewDecisionError(
                "Review context path could not be safely normalized"
            ) from exc

    @staticmethod
    def _is_within(path: Path, root: Path) -> bool:
        try:
            path.relative_to(root)
            return True
        except ValueError:
            return False

    @staticmethod
    def _validate_required_text(field_name: str, value: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise HumanReviewDecisionError(f"{field_name} is required")

        return " ".join(value.split())

    def _validate_reviewer_reference(self, value: str) -> str:
        reference = self._validate_required_text(
            "reviewer_reference",
            value,
        )

        if len(reference) > 120:
            raise HumanReviewDecisionError(
                "reviewer_reference must be 120 characters or fewer"
            )

        if not all(
            character.isalnum() or character in {"_", "-", "."}
            for character in reference
        ):
            raise HumanReviewDecisionError(
                "reviewer_reference must use only letters, numbers, dots, "
                "hyphens, or underscores"
            )

        return reference

    def _validate_decision_reason(self, value: str) -> str:
        reason = self._validate_required_text("decision_reason", value)

        if len(reason) > 1000:
            raise HumanReviewDecisionError(
                "decision_reason must be 1000 characters or fewer"
            )

        return reason
