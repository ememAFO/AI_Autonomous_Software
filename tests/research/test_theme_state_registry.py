from pathlib import Path

import pytest

from src.hermes.theme_state_registry import (
    DuplicateStateEventError,
    InvalidTransitionError,
    RegistryIntegrityError,
    ThemeNotFoundError,
    ThemeStateRegistry,
    ThemeStateRegistryError,
)

def make_registry(
    path: str = "reports/intelligence/test_theme_state_registry.json",
) -> ThemeStateRegistry:
    registry_path = Path(path)

    if registry_path.exists():
        registry_path.unlink()

    return ThemeStateRegistry(registry_path=path)

def register_theme(registry: ThemeStateRegistry):
    return registry.register_theme(
        theme_id="lead_follow_up_001",
        theme_name="Lead follow-up automation",
        trigger="trend_detected",
        reason="Repeated lead follow-up pain found in source evidence.",
        changed_by="HermesMemoryTrendDetector",
        related_artifact_id="trend_report_001",
        policy_version="2026-06-08.v1",
        run_id="pipeline_test_001",
    )


def test_theme_state_registry_registers_theme_as_researched():
    registry = make_registry()

    event = register_theme(registry)

    assert event.previous_state is None
    assert event.new_state == "RESEARCHED"
    assert registry.get_current_state("lead_follow_up_001") == "RESEARCHED"


def test_theme_state_registry_allows_valid_transition():
    registry = make_registry(
        "reports/intelligence/test_theme_state_registry_valid_transition.json"
    )
    register_theme(registry)

    event = registry.transition(
        theme_id="lead_follow_up_001",
        theme_name="Lead follow-up automation",
        new_state="VALIDATION_READY",
        trigger="validation_readiness_passed",
        reason="Theme met validation readiness criteria.",
        changed_by="ThemeValidationReadinessEvaluator",
        related_artifact_id="readiness_report_001",
        policy_version="2026-06-08.v1",
        run_id="pipeline_test_002",
    )

    assert event.previous_state == "RESEARCHED"
    assert event.new_state == "VALIDATION_READY"
    assert registry.get_current_state("lead_follow_up_001") == "VALIDATION_READY"


def test_theme_state_registry_blocks_invalid_transition():
    registry = make_registry(
        "reports/intelligence/test_theme_state_registry_invalid_transition.json"
    )
    register_theme(registry)

    with pytest.raises(ThemeStateRegistryError):
        registry.transition(
            theme_id="lead_follow_up_001",
            theme_name="Lead follow-up automation",
            new_state="READY_FOR_REVIEW",
            trigger="manual_bypass_attempt",
            reason="Trying to skip validation.",
            changed_by="Test",
            related_artifact_id="none",
            policy_version="2026-06-08.v1",
            run_id="pipeline_test_003",
        )


def test_theme_state_registry_blocks_duplicate_registration():
    registry = make_registry(
        "reports/intelligence/test_theme_state_registry_duplicate.json"
    )
    register_theme(registry)

    with pytest.raises(ThemeStateRegistryError):
        register_theme(registry)


def test_theme_state_registry_blocks_unknown_state():
    registry = make_registry(
        "reports/intelligence/test_theme_state_registry_unknown_state.json"
    )
    register_theme(registry)

    with pytest.raises(ThemeStateRegistryError):
        registry.transition(
            theme_id="lead_follow_up_001",
            theme_name="Lead follow-up automation",
            new_state="BUILD_NOW",
            trigger="unsafe_build_jump",
            reason="Trying to jump to build.",
            changed_by="Test",
            related_artifact_id="none",
            policy_version="2026-06-08.v1",
            run_id="pipeline_test_004",
        )


def test_theme_state_registry_blocks_unregistered_theme_transition():
    registry = make_registry(
        "reports/intelligence/test_theme_state_registry_unregistered.json"
    )

    with pytest.raises(ThemeStateRegistryError):
        registry.transition(
            theme_id="missing_theme",
            theme_name="Missing theme",
            new_state="VALIDATION_READY",
            trigger="missing_registration",
            reason="No initial RESEARCHED state exists.",
            changed_by="Test",
            related_artifact_id="none",
            policy_version="2026-06-08.v1",
            run_id="pipeline_test_005",
        )


def test_theme_state_registry_blocks_theme_name_mismatch():
    registry = make_registry(
        "reports/intelligence/test_theme_state_registry_name_mismatch.json"
    )
    register_theme(registry)

    with pytest.raises(ThemeStateRegistryError):
        registry.transition(
            theme_id="lead_follow_up_001",
            theme_name="Different theme name",
            new_state="VALIDATION_READY",
            trigger="name_mismatch",
            reason="Theme name should not silently change.",
            changed_by="Test",
            related_artifact_id="none",
            policy_version="2026-06-08.v1",
            run_id="pipeline_test_006",
        )


def test_theme_state_registry_is_append_only():
    registry = make_registry(
        "reports/intelligence/test_theme_state_registry_append_only.json"
    )
    register_theme(registry)

    registry.transition(
        theme_id="lead_follow_up_001",
        theme_name="Lead follow-up automation",
        new_state="VALIDATION_READY",
        trigger="validation_readiness_passed",
        reason="Theme met validation readiness criteria.",
        changed_by="ThemeValidationReadinessEvaluator",
        related_artifact_id="readiness_report_001",
        policy_version="2026-06-08.v1",
        run_id="pipeline_test_007",
    )

    events = registry.list_events_for_theme("lead_follow_up_001")

    assert len(events) == 2
    assert events[0].new_state == "RESEARCHED"
    assert events[1].new_state == "VALIDATION_READY"


def test_theme_state_registry_blocks_unsafe_registry_path():
    with pytest.raises(ThemeStateRegistryError):
        ThemeStateRegistry(registry_path="../../unsafe.json")


def test_theme_state_registry_blocks_non_json_registry_path():
    with pytest.raises(ThemeStateRegistryError):
        ThemeStateRegistry(
            registry_path="reports/intelligence/test_theme_state_registry.txt"
        )


def test_theme_state_registry_blocks_invalid_json():
    path = Path("reports/intelligence/test_invalid_theme_state_registry.json")

    if path.exists():
        path.unlink()

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{not valid json", encoding="utf-8")

    registry = ThemeStateRegistry(registry_path=path)

    with pytest.raises(ThemeStateRegistryError):
        registry.list_events()

def test_theme_state_registry_blocks_duplicate_state_event():
    registry = make_registry(
        "reports/intelligence/test_theme_state_registry_duplicate_state.json"
    )
    register_theme(registry)

    registry.transition(
        theme_id="lead_follow_up_001",
        theme_name="Lead follow-up automation",
        new_state="VALIDATION_READY",
        trigger="validation_readiness_passed",
        reason="Theme met validation readiness criteria.",
        changed_by="ThemeValidationReadinessEvaluator",
        related_artifact_id="readiness_report_001",
        policy_version="2026-06-08.v1",
        run_id="pipeline_test_duplicate_state_001",
    )

    with pytest.raises(DuplicateStateEventError):
        registry.transition(
            theme_id="lead_follow_up_001",
            theme_name="Lead follow-up automation",
            new_state="VALIDATION_READY",
            trigger="duplicate_transition",
            reason="Trying to repeat the same state.",
            changed_by="Test",
            related_artifact_id="none",
            policy_version="2026-06-08.v1",
            run_id="pipeline_test_duplicate_state_002",
        )


def test_theme_state_registry_uses_specific_missing_theme_error():
    registry = make_registry(
        "reports/intelligence/test_theme_state_registry_missing_theme_specific.json"
    )

    with pytest.raises(ThemeNotFoundError):
        registry.transition(
            theme_id="missing_theme",
            theme_name="Missing theme",
            new_state="VALIDATION_READY",
            trigger="missing_registration",
            reason="No initial RESEARCHED state exists.",
            changed_by="Test",
            related_artifact_id="none",
            policy_version="2026-06-08.v1",
            run_id="pipeline_test_missing_specific",
        )


def test_theme_state_registry_uses_specific_invalid_transition_error():
    registry = make_registry(
        "reports/intelligence/test_theme_state_registry_invalid_transition_specific.json"
    )
    register_theme(registry)

    with pytest.raises(InvalidTransitionError):
        registry.transition(
            theme_id="lead_follow_up_001",
            theme_name="Lead follow-up automation",
            new_state="READY_FOR_REVIEW",
            trigger="manual_bypass_attempt",
            reason="Trying to skip validation.",
            changed_by="Test",
            related_artifact_id="none",
            policy_version="2026-06-08.v1",
            run_id="pipeline_test_invalid_specific",
        )


def test_theme_state_registry_writes_record_hash():
    registry = make_registry(
        "reports/intelligence/test_theme_state_registry_record_hash.json"
    )

    event = register_theme(registry)

    assert event.record_hash
    assert len(event.record_hash) == 64


def test_theme_state_registry_verify_integrity_passes_for_valid_registry():
    registry = make_registry(
        "reports/intelligence/test_theme_state_registry_integrity_valid.json"
    )

    register_theme(registry)

    registry.verify_integrity()


def test_theme_state_registry_verify_integrity_detects_modified_record():
    path = Path("reports/intelligence/test_theme_state_registry_integrity_modified.json")

    if path.exists():
        path.unlink()

    registry = ThemeStateRegistry(registry_path=path)
    register_theme(registry)

    data = path.read_text(encoding="utf-8")
    data = data.replace("Lead follow-up automation", "Tampered theme name")
    path.write_text(data, encoding="utf-8")

    with pytest.raises(RegistryIntegrityError):
        registry.verify_integrity()

def test_theme_state_registry_blocks_generic_return_from_ready_for_review():
    registry = make_registry(
        "reports/intelligence/"
        "test_theme_state_registry_generic_review_return.json"
    )
    register_theme(registry)

    registry.transition(
        theme_id="lead_follow_up_001",
        theme_name="Lead follow-up automation",
        new_state="VALIDATION_READY",
        trigger="validation_readiness_passed",
        reason="Theme met validation readiness criteria.",
        changed_by="ThemeValidationReadinessEvaluator",
        related_artifact_id="readiness_report_001",
        policy_version="2026-06-08.v1",
        run_id="pipeline_test_review_return_001",
    )

    registry.transition(
        theme_id="lead_follow_up_001",
        theme_name="Lead follow-up automation",
        new_state="VALIDATING",
        trigger="validation_plan_created",
        reason="Validation plan created.",
        changed_by="ThemeValidationPlanGenerator",
        related_artifact_id="validation_plan_001",
        policy_version="2026-06-08.v1",
        run_id="pipeline_test_review_return_002",
    )

    registry.transition(
        theme_id="lead_follow_up_001",
        theme_name="Lead follow-up automation",
        new_state="READY_FOR_REVIEW",
        trigger="validation_gate_passed",
        reason="Validation evidence met human review threshold.",
        changed_by="ValidationGate",
        related_artifact_id="validation_summary_001",
        policy_version="2026-06-08.v1",
        run_id="pipeline_test_review_return_003",
    )

    with pytest.raises(InvalidTransitionError):
        registry.transition(
            theme_id="lead_follow_up_001",
            theme_name="Lead follow-up automation",
            new_state="VALIDATING",
            trigger="manual_state_update",
            reason="Unsafe direct return attempt.",
            changed_by="update_theme_state_cli",
            related_artifact_id="manual_cli_update",
            policy_version="2026-06-08.v1",
            run_id="pipeline_test_review_return_004",
        )

def test_theme_state_registry_blocks_terminal_state_transition():
    registry = make_registry(
        "reports/intelligence/test_theme_state_registry_terminal_state.json"
    )
    register_theme(registry)

    registry.transition(
        theme_id="lead_follow_up_001",
        theme_name="Lead follow-up automation",
        new_state="VALIDATION_READY",
        trigger="validation_readiness_passed",
        reason="Theme met validation readiness criteria.",
        changed_by="ThemeValidationReadinessEvaluator",
        related_artifact_id="readiness_report_001",
        policy_version="2026-06-08.v1",
        run_id="pipeline_test_terminal_001",
    )

    registry.transition(
        theme_id="lead_follow_up_001",
        theme_name="Lead follow-up automation",
        new_state="VALIDATING",
        trigger="validation_plan_created",
        reason="Validation plan created.",
        changed_by="ThemeValidationPlanGenerator",
        related_artifact_id="validation_plan_001",
        policy_version="2026-06-08.v1",
        run_id="pipeline_test_terminal_002",
    )

    registry.transition(
        theme_id="lead_follow_up_001",
        theme_name="Lead follow-up automation",
        new_state="READY_FOR_REVIEW",
        trigger="validation_gate_passed",
        reason="Validation evidence met human review threshold.",
        changed_by="ValidationGate",
        related_artifact_id="validation_summary_001",
        policy_version="2026-06-08.v1",
        run_id="pipeline_test_terminal_003",
    )

    with pytest.raises(InvalidTransitionError):
        registry.transition(
            theme_id="lead_follow_up_001",
            theme_name="Lead follow-up automation",
            new_state="REJECTED",
            trigger="attempt_terminal_change",
            reason="Trying to move away from terminal review state.",
            changed_by="Test",
            related_artifact_id="none",
            policy_version="2026-06-08.v1",
            run_id="pipeline_test_terminal_004",
        )
