from pathlib import Path

import pytest

from src.hermes.human_review_decision import (
    HumanReviewDecisionError,
    HumanReviewDecisionService,
)
from src.hermes.theme_state_registry import ThemeStateRegistry
from src.hermes.validation_evidence_log import ValidationEvidenceLog
from src.hermes.validation_evidence_summary import (
    ValidationEvidenceSummarizer,
)


THEME_ID = "lead_follow_up_001"
THEME_NAME = "lead + follow up"
POLICY_VERSION = "2026-06-08.v1"


def clean_path(path: str | Path) -> None:
    file_path = Path(path)

    if file_path.exists():
        file_path.unlink()


def make_components(
    prefix: str,
) -> tuple[
    HumanReviewDecisionService,
    ThemeStateRegistry,
    ValidationEvidenceLog,
    str,
]:
    state_path = (
        "reports/intelligence/"
        f"test_human_review_decision_{prefix}_state_registry.json"
    )
    evidence_path = (
        "reports/intelligence/"
        f"test_human_review_decision_{prefix}_evidence_log.json"
    )
    context_path = Path(
        "reports/intelligence/"
        "test_human_review_decision_contexts/"
        f"{prefix}_context.md"
    )

    clean_path(state_path)
    clean_path(evidence_path)

    context_path.parent.mkdir(parents=True, exist_ok=True)
    context_path.write_text(
        "# Validation Evidence Repair Context\n",
        encoding="utf-8",
    )

    registry = ThemeStateRegistry(registry_path=state_path)
    evidence_log = ValidationEvidenceLog(log_path=evidence_path)

    service = HumanReviewDecisionService(
        state_registry=registry,
        evidence_summarizer=ValidationEvidenceSummarizer(evidence_log),
    )

    return service, registry, evidence_log, str(context_path)


def register_theme_as_ready_for_review(
    registry: ThemeStateRegistry,
    *,
    changed_by: str = "ValidationGate",
) -> None:
    registry.register_theme(
        theme_id=THEME_ID,
        theme_name=THEME_NAME,
        trigger="trend_detected",
        reason="Repeated lead follow-up pain found.",
        changed_by="HermesMemoryTrendDetector",
        related_artifact_id="trend_report_001",
        policy_version=POLICY_VERSION,
        run_id="human_review_decision_001",
    )

    registry.transition(
        theme_id=THEME_ID,
        theme_name=THEME_NAME,
        new_state="VALIDATION_READY",
        trigger="validation_readiness_passed",
        reason="Theme met validation readiness criteria.",
        changed_by="ThemeValidationReadinessEvaluator",
        related_artifact_id="readiness_report_001",
        policy_version=POLICY_VERSION,
        run_id="human_review_decision_002",
    )

    registry.transition(
        theme_id=THEME_ID,
        theme_name=THEME_NAME,
        new_state="VALIDATING",
        trigger="validation_plan_created",
        reason="Validation plan created.",
        changed_by="ThemeValidationPlanGenerator",
        related_artifact_id="validation_plan_001",
        policy_version=POLICY_VERSION,
        run_id="human_review_decision_003",
    )

    registry.transition(
        theme_id=THEME_ID,
        theme_name=THEME_NAME,
        new_state="READY_FOR_REVIEW",
        trigger="validation_gate_passed",
        reason="Legacy gate event created before evidence repair.",
        changed_by=changed_by,
        related_artifact_id="validation_progress_snapshot_001",
        policy_version=POLICY_VERSION,
        run_id="human_review_decision_004",
    )


def add_template_evidence(
    log: ValidationEvidenceLog,
) -> None:
    for index in range(5):
        log.add_entry(
            theme=THEME_NAME,
            validation_plan_path=(
                "reports/intelligence/validation_plans/"
                "lead_and_follow_up_validation_plan.md"
            ),
            evidence_type="customer_interview",
            evidence_summary=(
                "Participant/Signal: small_business_owner_003. "
                "Finding: REPLACE_WITH_REAL_FINDING"
            ),
            source_reference=f"legacy_interview_{index}",
            signal_strength="strong",
            supports_validation=True,
            notes="Primary customer interview evidence.",
        )


def add_clean_evidence(
    log: ValidationEvidenceLog,
) -> None:
    for index in range(5):
        log.add_entry(
            theme=THEME_NAME,
            validation_plan_path=(
                "reports/intelligence/validation_plans/"
                "lead_and_follow_up_validation_plan.md"
            ),
            evidence_type="customer_interview",
            evidence_summary=(
                "Owner confirmed delayed follow-up can lose bookings."
            ),
            source_reference=f"interview_{index}",
            signal_strength="strong" if index < 3 else "medium",
            supports_validation=True,
            notes="Primary customer interview evidence.",
        )


def test_human_review_decision_returns_theme_to_validation_after_evidence_repair():
    service, registry, evidence_log, context_path = make_components("success")

    register_theme_as_ready_for_review(registry)
    add_template_evidence(evidence_log)

    state_event_count_before = len(
        registry.list_events_for_theme(THEME_ID)
    )
    evidence_count_before = len(
        evidence_log.list_entries_for_theme(THEME_NAME)
    )

    result = service.return_to_validation(
        theme_id=THEME_ID,
        theme_name=THEME_NAME,
        reviewer_reference="reviewer_001",
        decision_reason=(
            "Current evidence contains template markers and must be replaced "
            "before any further review."
        ),
        review_context_path=context_path,
        policy_version=POLICY_VERSION,
        run_id="human_review_return_success_001",
    )

    assert result.previous_state == "READY_FOR_REVIEW"
    assert result.new_state == "VALIDATING"
    assert result.decision_status == "RETURNED_TO_VALIDATION"
    assert result.evidence_status == "EVIDENCE_NEEDS_VERIFICATION"
    assert registry.get_current_state(THEME_ID) == "VALIDATING"
    assert len(registry.list_events_for_theme(THEME_ID)) == (
        state_event_count_before + 1
    )
    assert len(evidence_log.list_entries_for_theme(THEME_NAME)) == (
        evidence_count_before
    )

    latest_event = registry.list_events_for_theme(THEME_ID)[-1]

    assert latest_event.trigger == (
        ThemeStateRegistry.HUMAN_REVIEW_RETURN_TRIGGER
    )
    assert latest_event.changed_by == (
        ThemeStateRegistry.HUMAN_REVIEW_RETURN_ACTOR
    )
    assert "reviewer_001" in latest_event.reason
    assert "EVIDENCE_NEEDS_VERIFICATION" in latest_event.reason

    registry.verify_integrity()


def test_human_review_decision_blocks_when_evidence_is_still_ready():
    service, registry, evidence_log, context_path = make_components("ready")

    register_theme_as_ready_for_review(registry)
    add_clean_evidence(evidence_log)

    with pytest.raises(
        HumanReviewDecisionError,
        match="requires repair or further validation",
    ):
        service.return_to_validation(
            theme_id=THEME_ID,
            theme_name=THEME_NAME,
            reviewer_reference="reviewer_001",
            decision_reason="Return to validation.",
            review_context_path=context_path,
            policy_version=POLICY_VERSION,
            run_id="human_review_return_ready_001",
        )


def test_human_review_decision_blocks_invalid_gate_provenance():
    service, registry, evidence_log, context_path = make_components("provenance")

    register_theme_as_ready_for_review(
        registry,
        changed_by="ManualStateUpdate",
    )
    add_template_evidence(evidence_log)

    with pytest.raises(
        HumanReviewDecisionError,
        match="recorded by ValidationGate",
    ):
        service.return_to_validation(
            theme_id=THEME_ID,
            theme_name=THEME_NAME,
            reviewer_reference="reviewer_001",
            decision_reason="Evidence requires repair.",
            review_context_path=context_path,
            policy_version=POLICY_VERSION,
            run_id="human_review_return_provenance_001",
        )


def test_human_review_decision_blocks_invalid_reviewer_reference():
    service, registry, evidence_log, context_path = make_components("reviewer")

    register_theme_as_ready_for_review(registry)
    add_template_evidence(evidence_log)

    with pytest.raises(
        HumanReviewDecisionError,
        match="letters, numbers",
    ):
        service.return_to_validation(
            theme_id=THEME_ID,
            theme_name=THEME_NAME,
            reviewer_reference="reviewer@example.com",
            decision_reason="Evidence requires repair.",
            review_context_path=context_path,
            policy_version=POLICY_VERSION,
            run_id="human_review_return_reviewer_001",
        )


def test_human_review_decision_blocks_unsafe_or_missing_context_path():
    service, registry, evidence_log, _ = make_components("context")

    register_theme_as_ready_for_review(registry)
    add_template_evidence(evidence_log)

    with pytest.raises(
        HumanReviewDecisionError,
        match="reports/intelligence",
    ):
        service.return_to_validation(
            theme_id=THEME_ID,
            theme_name=THEME_NAME,
            reviewer_reference="reviewer_001",
            decision_reason="Evidence requires repair.",
            review_context_path="../../outside.md",
            policy_version=POLICY_VERSION,
            run_id="human_review_return_context_001",
        )

    with pytest.raises(
        HumanReviewDecisionError,
        match="does not exist",
    ):
        service.return_to_validation(
            theme_id=THEME_ID,
            theme_name=THEME_NAME,
            reviewer_reference="reviewer_001",
            decision_reason="Evidence requires repair.",
            review_context_path=(
                "reports/intelligence/"
                "test_human_review_decision_contexts/missing.md"
            ),
            policy_version=POLICY_VERSION,
            run_id="human_review_return_context_002",
        )
