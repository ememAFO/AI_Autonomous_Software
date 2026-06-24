from pathlib import Path

import pytest

from src.hermes.theme_state_registry import (
    ThemeNotFoundError,
    ThemeStateRegistry,
)
from src.hermes.validation_evidence_log import ValidationEvidenceLog
from src.hermes.validation_evidence_summary import ValidationEvidenceSummarizer
from src.hermes.validation_gate import ValidationGate


THEME_ID = "lead_follow_up_001"
THEME_NAME = "lead + follow up"
POLICY_VERSION = "2026-06-08.v1"


def make_state_registry(
    path: str = "reports/intelligence/test_validation_gate_state_registry.json",
) -> ThemeStateRegistry:
    registry_path = Path(path)

    if registry_path.exists():
        registry_path.unlink()

    return ThemeStateRegistry(registry_path=path)


def make_evidence_log(
    path: str = "reports/intelligence/test_validation_gate_evidence_log.json",
) -> ValidationEvidenceLog:
    log_path = Path(path)

    if log_path.exists():
        log_path.unlink()

    return ValidationEvidenceLog(log_path=path)


def register_theme_as_validating(registry: ThemeStateRegistry) -> None:
    registry.register_theme(
        theme_id=THEME_ID,
        theme_name=THEME_NAME,
        trigger="trend_detected",
        reason="Repeated lead follow-up pain found.",
        changed_by="HermesMemoryTrendDetector",
        related_artifact_id="trend_report_001",
        policy_version=POLICY_VERSION,
        run_id="pipeline_gate_test_001",
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
        run_id="pipeline_gate_test_002",
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
        run_id="pipeline_gate_test_003",
    )


def add_ready_evidence(log: ValidationEvidenceLog) -> None:
    for index in range(5):
        signal_strength = "strong" if index < 3 else "medium"

        log.add_entry(
            theme=THEME_NAME,
            validation_plan_path=(
                "reports/intelligence/validation_plans/"
                "lead_and_follow_up_validation_plan.md"
            ),
            evidence_type="customer_interview",
            evidence_summary=(
                "User confirmed delayed lead follow-up creates lost sales."
            ),
            source_reference=f"Interview {index + 1}",
            signal_strength=signal_strength,
            supports_validation=True,
            source_trust=ValidationEvidenceLog.HUMAN_ATTESTED_FIRST_PARTY,
        )


def make_gate(
    *,
    registry_path: str = "reports/intelligence/test_validation_gate_state_registry.json",
    evidence_log_path: str = "reports/intelligence/test_validation_gate_evidence_log.json",
) -> tuple[ValidationGate, ThemeStateRegistry, ValidationEvidenceLog]:
    registry = make_state_registry(registry_path)
    evidence_log = make_evidence_log(evidence_log_path)

    gate = ValidationGate(
        state_registry=registry,
        evidence_summarizer=ValidationEvidenceSummarizer(evidence_log),
    )

    return gate, registry, evidence_log


def test_validation_gate_moves_validating_theme_to_ready_for_review():
    gate, registry, evidence_log = make_gate()

    register_theme_as_validating(registry)
    add_ready_evidence(evidence_log)

    result = gate.evaluate(
        theme_id=THEME_ID,
        theme_name=THEME_NAME,
        policy_version=POLICY_VERSION,
        run_id="pipeline_gate_test_004",
        related_artifact_id="validation_evidence_summary_001",
    )

    assert result.gate_status == "READY_FOR_HUMAN_REVIEW"
    assert result.state_changed is True
    assert result.new_state == "READY_FOR_REVIEW"
    assert registry.get_current_state(THEME_ID) == "READY_FOR_REVIEW"


def test_validation_gate_blocks_when_theme_is_not_validating():
    gate, registry, evidence_log = make_gate(
        registry_path=(
            "reports/intelligence/"
            "test_validation_gate_not_validating_state_registry.json"
        ),
        evidence_log_path=(
            "reports/intelligence/"
            "test_validation_gate_not_validating_evidence_log.json"
        ),
    )

    registry.register_theme(
        theme_id=THEME_ID,
        theme_name=THEME_NAME,
        trigger="trend_detected",
        reason="Repeated lead follow-up pain found.",
        changed_by="HermesMemoryTrendDetector",
        related_artifact_id="trend_report_001",
        policy_version=POLICY_VERSION,
        run_id="pipeline_gate_not_validating_001",
    )

    add_ready_evidence(evidence_log)

    result = gate.evaluate(
        theme_id=THEME_ID,
        theme_name=THEME_NAME,
        policy_version=POLICY_VERSION,
        run_id="pipeline_gate_not_validating_002",
        related_artifact_id="validation_evidence_summary_001",
    )

    assert result.gate_status == "BLOCKED"
    assert result.state_changed is False
    assert result.current_state == "RESEARCHED"
    assert registry.get_current_state(THEME_ID) == "RESEARCHED"


def test_validation_gate_blocks_when_evidence_is_early_signal():
    gate, registry, evidence_log = make_gate(
        registry_path=(
            "reports/intelligence/"
            "test_validation_gate_early_signal_state_registry.json"
        ),
        evidence_log_path=(
            "reports/intelligence/"
            "test_validation_gate_early_signal_evidence_log.json"
        ),
    )

    register_theme_as_validating(registry)

    evidence_log.add_entry(
        theme=THEME_NAME,
        validation_plan_path=(
            "reports/intelligence/validation_plans/"
            "lead_and_follow_up_validation_plan.md"
        ),
        evidence_type="customer_interview",
        evidence_summary="One user confirmed lead follow-up pain.",
        source_reference="Interview 1",
        signal_strength="strong",
        supports_validation=True,
        source_trust=ValidationEvidenceLog.HUMAN_ATTESTED_FIRST_PARTY,
    )

    result = gate.evaluate(
        theme_id=THEME_ID,
        theme_name=THEME_NAME,
        policy_version=POLICY_VERSION,
        run_id="pipeline_gate_early_signal_001",
        related_artifact_id="validation_evidence_summary_001",
    )

    assert result.gate_status == "BLOCKED"
    assert result.evidence_status == "EARLY_SUPPORTING_SIGNAL"
    assert result.state_changed is False
    assert registry.get_current_state(THEME_ID) == "VALIDATING"


def test_validation_gate_blocks_when_evidence_is_negative():
    gate, registry, evidence_log = make_gate(
        registry_path=(
            "reports/intelligence/"
            "test_validation_gate_negative_state_registry.json"
        ),
        evidence_log_path=(
            "reports/intelligence/"
            "test_validation_gate_negative_evidence_log.json"
        ),
    )

    register_theme_as_validating(registry)

    for index in range(3):
        evidence_log.add_entry(
            theme=THEME_NAME,
            validation_plan_path=(
                "reports/intelligence/validation_plans/"
                "lead_and_follow_up_validation_plan.md"
            ),
            evidence_type="customer_interview",
            evidence_summary="User said the problem is already solved.",
            source_reference=f"Interview {index + 1}",
            signal_strength="negative",
            supports_validation=False,
            source_trust=ValidationEvidenceLog.HUMAN_ATTESTED_FIRST_PARTY,
        )

    result = gate.evaluate(
        theme_id=THEME_ID,
        theme_name=THEME_NAME,
        policy_version=POLICY_VERSION,
        run_id="pipeline_gate_negative_001",
        related_artifact_id="validation_evidence_summary_001",
    )

    assert result.gate_status == "BLOCKED"
    assert result.evidence_status == "NEGATIVE_OR_WEAK_SIGNAL"
    assert result.state_changed is False
    assert registry.get_current_state(THEME_ID) == "VALIDATING"


def test_validation_gate_requires_registered_theme():
    gate, _, _ = make_gate(
        registry_path=(
            "reports/intelligence/"
            "test_validation_gate_missing_theme_state_registry.json"
        ),
        evidence_log_path=(
            "reports/intelligence/"
            "test_validation_gate_missing_theme_evidence_log.json"
        ),
    )

    with pytest.raises(ThemeNotFoundError):
        gate.evaluate(
            theme_id="missing_theme",
            theme_name=THEME_NAME,
            policy_version=POLICY_VERSION,
            run_id="pipeline_gate_missing_theme_001",
            related_artifact_id="validation_evidence_summary_001",
        )
