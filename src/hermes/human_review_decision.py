from dataclasses import dataclass
from pathlib import Path

from src.hermes.human_review_packet import (
    HumanReviewPacketRegistry,
    HumanReviewPacketRegistryEntry,
    HumanReviewPacketRegistryError,
)
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


@dataclass(frozen=True)
class HumanReviewResolutionResult:
    theme_id: str
    theme_name: str
    previous_state: str
    new_state: str
    decision: str
    reviewer_reference: str
    decision_reason: str
    review_packet_id: str
    review_packet_path: str
    state_event_id: str
    policy_version: str
    run_id: str
    timestamp: str
    recommended_next_action: str


class HumanReviewResolutionService:
    """
    Records final human-review outcomes after a valid Human Review Packet.

    This service can move a review-ready theme only to MVP_PLANNING or
    REJECTED. MVP_PLANNING is a bounded planning state and does not approve
    implementation, integration, deployment, or autonomous execution.

    Reviewer references are audit identifiers only; this local workflow does
    not provide identity authentication or role-based authorization.
    """

    REQUIRED_CURRENT_STATE = "READY_FOR_REVIEW"
    REQUIRED_EVIDENCE_STATUS = "READY_FOR_HUMAN_REVIEW"
    REQUIRED_GATE_TRIGGER = "validation_gate_passed"
    REQUIRED_GATE_ACTOR = "ValidationGate"
    REQUIRED_PACKET_STATUS = "PENDING_HUMAN_DECISION"

    APPROVE_MVP_PLANNING = "APPROVE_MVP_PLANNING"
    REJECT = "REJECT"
    ALLOWED_DECISIONS = {
        APPROVE_MVP_PLANNING,
        REJECT,
    }

    def __init__(
        self,
        *,
        state_registry: ThemeStateRegistry | None = None,
        evidence_summarizer: ValidationEvidenceSummarizer | None = None,
        packet_registry: HumanReviewPacketRegistry | None = None,
    ):
        self.state_registry = state_registry or ThemeStateRegistry()
        self.evidence_summarizer = (
            evidence_summarizer or ValidationEvidenceSummarizer()
        )
        self.packet_registry = packet_registry or HumanReviewPacketRegistry()
        self.project_root = Path.cwd().resolve()
        self.path_normalizer = ProjectPathNormalizer()

    def resolve(
        self,
        *,
        theme_id: str,
        theme_name: str,
        decision: str,
        reviewer_reference: str,
        decision_reason: str,
        review_packet_id: str,
        policy_version: str,
        run_id: str,
    ) -> HumanReviewResolutionResult:
        theme_id = self._validate_required_text("theme_id", theme_id)
        theme_name = self._validate_required_text("theme_name", theme_name)
        decision = self._normalize_decision(decision)
        reviewer_reference = self._validate_reviewer_reference(
            reviewer_reference
        )
        decision_reason = self._validate_decision_reason(decision_reason)
        review_packet_id = self._validate_packet_id(review_packet_id)
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
        self._validate_review_ready_event(
            latest_event=latest_event,
            theme_name=theme_name,
            policy_version=policy_version,
        )

        evidence_summary = self.evidence_summarizer.summarize_theme(theme_name)
        if evidence_summary.status != self.REQUIRED_EVIDENCE_STATUS:
            raise HumanReviewDecisionError(
                "Human review resolution requires current evidence status "
                f"{self.REQUIRED_EVIDENCE_STATUS}, got {evidence_summary.status}"
            )

        packet_entry = self._find_registered_packet(
            packet_id=review_packet_id,
        )
        packet_path = self._validate_packet_provenance(
            packet_entry=packet_entry,
            latest_event=latest_event,
            theme_id=theme_id,
            theme_name=theme_name,
            policy_version=policy_version,
        )

        state_reason = (
            "Human review resolution recorded. "
            f"Decision: {decision}. "
            f"Reviewer Reference: {reviewer_reference}. "
            f"Decision Reason: {decision_reason}. "
            f"Review Packet ID: {review_packet_id}."
        )

        try:
            if decision == self.APPROVE_MVP_PLANNING:
                event = (
                    self.state_registry.approve_mvp_planning_after_human_review(
                        theme_id=theme_id,
                        theme_name=theme_name,
                        reason=state_reason,
                        related_artifact_id=packet_path,
                        policy_version=policy_version,
                        run_id=run_id,
                    )
                )
                recommended_next_action = (
                    "Create a controlled MVP planning artefact with scope, "
                    "security constraints, failure criteria, and a separate "
                    "human approval before implementation work."
                )
            else:
                event = self.state_registry.reject_after_human_review(
                    theme_id=theme_id,
                    theme_name=theme_name,
                    reason=state_reason,
                    related_artifact_id=packet_path,
                    policy_version=policy_version,
                    run_id=run_id,
                )
                recommended_next_action = (
                    "Keep the rejection event and evidence history intact. "
                    "Archive the theme only through the controlled lifecycle "
                    "when no further review is required."
                )
        except (
            InvalidTransitionError,
            ThemeNotFoundError,
            ThemeStateRegistryError,
        ) as exc:
            raise HumanReviewDecisionError(
                "Human review resolution could not record the state transition"
            ) from exc

        return HumanReviewResolutionResult(
            theme_id=theme_id,
            theme_name=theme_name,
            previous_state=event.previous_state or "",
            new_state=event.new_state,
            decision=decision,
            reviewer_reference=reviewer_reference,
            decision_reason=decision_reason,
            review_packet_id=review_packet_id,
            review_packet_path=packet_path,
            state_event_id=event.event_id,
            policy_version=policy_version,
            run_id=run_id,
            timestamp=event.timestamp,
            recommended_next_action=recommended_next_action,
        )

    def _validate_review_ready_event(
        self,
        *,
        latest_event,
        theme_name: str,
        policy_version: str,
    ) -> None:
        if latest_event.theme_name != theme_name:
            raise HumanReviewDecisionError(
                "Theme name does not match the registered state history"
            )

        if latest_event.new_state != self.REQUIRED_CURRENT_STATE:
            raise HumanReviewDecisionError(
                "Human review resolution requires current state "
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

        if latest_event.policy_version != policy_version:
            raise HumanReviewDecisionError(
                "Requested policy version does not match the validation gate event"
            )

    def _find_registered_packet(
        self,
        *,
        packet_id: str,
    ) -> HumanReviewPacketRegistryEntry:
        try:
            matches = [
                entry
                for entry in self.packet_registry.list_entries()
                if entry.packet_id == packet_id
            ]
        except HumanReviewPacketRegistryError as exc:
            raise HumanReviewDecisionError(
                "Human review packet registry could not be read"
            ) from exc

        if not matches:
            raise HumanReviewDecisionError(
                "Human review packet is not registered"
            )

        if len(matches) != 1:
            raise HumanReviewDecisionError(
                "Human review packet registry contains duplicate packet IDs"
            )

        return matches[0]

    def _validate_packet_provenance(
        self,
        *,
        packet_entry: HumanReviewPacketRegistryEntry,
        latest_event,
        theme_id: str,
        theme_name: str,
        policy_version: str,
    ) -> str:
        if packet_entry.theme_id != theme_id:
            raise HumanReviewDecisionError(
                "Human review packet theme ID does not match the decision"
            )

        if packet_entry.theme_name != theme_name:
            raise HumanReviewDecisionError(
                "Human review packet theme name does not match the decision"
            )

        if packet_entry.current_state != self.REQUIRED_CURRENT_STATE:
            raise HumanReviewDecisionError(
                "Human review packet is not registered for READY_FOR_REVIEW"
            )

        if packet_entry.review_status != self.REQUIRED_PACKET_STATUS:
            raise HumanReviewDecisionError(
                "Human review packet does not have pending human decision status"
            )

        if packet_entry.evidence_status != self.REQUIRED_EVIDENCE_STATUS:
            raise HumanReviewDecisionError(
                "Human review packet does not contain review-ready evidence"
            )

        if packet_entry.gate_event_id != latest_event.event_id:
            raise HumanReviewDecisionError(
                "Human review packet does not match the current validation gate event"
            )

        if packet_entry.policy_version != policy_version:
            raise HumanReviewDecisionError(
                "Human review packet policy version does not match the decision"
            )

        packet_path = self._resolve_packet_path(packet_entry.output_path)
        self._validate_packet_content(
            packet_path=packet_path,
            packet_entry=packet_entry,
            latest_event=latest_event,
            theme_id=theme_id,
            theme_name=theme_name,
            policy_version=policy_version,
        )
        return self._normalize_project_path(packet_path)

    def _resolve_packet_path(self, value: str) -> Path:
        value = self._validate_required_text("review_packet_path", value)
        candidate = Path(value)

        if candidate.is_absolute():
            resolved = candidate.resolve()
        else:
            resolved = (self.project_root / candidate).resolve()

        packet_root = self.packet_registry.packet_output_dir.resolve()

        if not self._is_within(resolved, packet_root):
            raise HumanReviewDecisionError(
                "Human review packet must stay inside the approved packet directory"
            )

        if resolved.suffix != ".md":
            raise HumanReviewDecisionError(
                "Human review packet must be a Markdown file"
            )

        if not resolved.is_file():
            raise HumanReviewDecisionError(
                "Human review packet Markdown file does not exist"
            )

        return resolved

    def _validate_packet_content(
        self,
        *,
        packet_path: Path,
        packet_entry: HumanReviewPacketRegistryEntry,
        latest_event,
        theme_id: str,
        theme_name: str,
        policy_version: str,
    ) -> None:
        try:
            content = packet_path.read_text(encoding="utf-8")
        except OSError as exc:
            raise HumanReviewDecisionError(
                "Human review packet Markdown file could not be read"
            ) from exc

        required_lines = {
            f"# Human Review Packet: {theme_name}",
            f"- Packet ID: {packet_entry.packet_id}",
            f"- Theme ID: {theme_id}",
            f"- Theme Name: {theme_name}",
            f"- Current State: {self.REQUIRED_CURRENT_STATE}",
            f"- Evidence Status: {self.REQUIRED_EVIDENCE_STATUS}",
            f"- Gate Event ID: {latest_event.event_id}",
            f"- Gate Policy Version: {policy_version}",
        }

        missing_lines = [
            line
            for line in required_lines
            if line not in content
        ]
        if missing_lines:
            raise HumanReviewDecisionError(
                "Human review packet content does not match its registered provenance"
            )

    @staticmethod
    def _is_within(path: Path, root: Path) -> bool:
        try:
            path.relative_to(root)
            return True
        except ValueError:
            return False

    def _normalize_project_path(self, path: Path) -> str:
        try:
            return self.path_normalizer.normalize(str(path))
        except PathNormalizerError as exc:
            raise HumanReviewDecisionError(
                "Human review packet path could not be safely normalized"
            ) from exc

    def _normalize_decision(self, value: str) -> str:
        decision = self._validate_required_text("decision", value).upper()

        if decision not in self.ALLOWED_DECISIONS:
            allowed = ", ".join(sorted(self.ALLOWED_DECISIONS))
            raise HumanReviewDecisionError(
                f"Unsupported human review decision: {decision}. Allowed: {allowed}"
            )

        return decision

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

    def _validate_packet_id(self, value: str) -> str:
        packet_id = self._validate_required_text("review_packet_id", value)

        if len(packet_id) > 160:
            raise HumanReviewDecisionError(
                "review_packet_id must be 160 characters or fewer"
            )

        if not all(
            character.isalnum() or character in {"_", "-", "."}
            for character in packet_id
        ):
            raise HumanReviewDecisionError(
                "review_packet_id must use only letters, numbers, dots, "
                "hyphens, or underscores"
            )

        return packet_id
