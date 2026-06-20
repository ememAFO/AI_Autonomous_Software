from pathlib import Path

import pytest

from src.hermes.theme_state_registry import ThemeStateRegistry
from src.hermes.validation_evidence_log import ValidationEvidenceLog
from src.hermes.validation_evidence_summary import ValidationEvidenceSummarizer
from src.hermes.validation_progress_snapshot import (
    ValidationProgressSnapshotError,
    ValidationProgressSnapshotGenerator,
)


THEME_ID = "lead_follow_up_001"
THEME_NAME = "lead + follow up"
POLICY_VERSION = "2026-06-08.v1"


def clean_path(path: str) -> None:
    file_path = Path(path)

    if file_path.exists():
        file_path.unlink()


def make_state_registry(
    path: str = "reports/intelligence/test_validation_progress_snapshot_state_registry.json",
) -> ThemeStateRegistry:
    clean_path(path)
    return ThemeStateRegistry(registry_path=path)


def make_evidence_log(
    path: str = "reports/intelligence/test_validation_progress_snapshot_evidence_log.json",
) -> ValidationEvidenceLog:
    clean_path(path)
    return ValidationEvidenceLog(log_path=path)


def make_generator(
    *,
    registry_path: str = "reports/intelligence/test_validation_progress_snapshot_state_registry.json",
    evidence_log_path: str = "reports/intelligence/test_validation_progress_snapshot_evidence_log.json",
) -> tuple[ValidationProgressSnapshotGenerator, ThemeStateRegistry, ValidationEvidenceLog]:
    registry = make_state_registry(registry_path)
    evidence_log = make_evidence_log(evidence_log_path)

    generator = ValidationProgressSnapshotGenerator(
        state_registry=registry,
        evidence_summarizer=ValidationEvidenceSummarizer(evidence_log),
    )

    return generator, registry, evidence_log


def register_theme_as_validating(registry: ThemeStateRegistry) -> None:
    registry.register_theme(
        theme_id=THEME_ID,
        theme_name=THEME_NAME,
        trigger="trend_detected",
        reason="Repeated lead follow-up pain found.",
        changed_by="HermesMemoryTrendDetector",
        related_artifact_id="trend_report_001",
        policy_version=POLICY_VERSION,
        run_id="validation_progress_snapshot_001",
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
        run_id="validation_progress_snapshot_002",
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
        run_id="validation_progress_snapshot_003",
    )


def add_ready_evidence(log: ValidationEvidenceLog) -> None:
    for index in range(5):
        log.add_entry(
            theme=THEME_NAME,
            validation_plan_path=(
                "reports/intelligence/validation_plans/"
                "lead_and_follow_up_validation_plan.md"
            ),
            evidence_type="customer_interview",
            evidence_summary="User confirmed delayed follow-up creates lost sales.",
            source_reference=f"Interview {index + 1}",
            signal_strength="strong" if index < 3 else "medium",
            supports_validation=True,
        )


def test_validation_progress_snapshot_reports_blocked_early_signal():
    generator, registry, evidence_log = make_generator()

    register_theme_as_validating(registry)

    evidence_log.add_entry(
        theme=THEME_NAME,
        validation_plan_path=(
            "reports/intelligence/validation_plans/"
            "lead_and_follow_up_validation_plan.md"
        ),
        evidence_type="customer_interview",
        evidence_summary="User confirmed delayed follow-up creates lost sales.",
        source_reference="Interview 1",
        signal_strength="strong",
        supports_validation=True,
    )

    evidence_log.add_entry(
        theme=THEME_NAME,
        validation_plan_path=(
            "reports/intelligence/validation_plans/"
            "lead_and_follow_up_validation_plan.md"
        ),
        evidence_type="competitor_check",
        evidence_summary="Existing CRM tools may be too broad.",
        source_reference="manual_competitor_check_001",
        signal_strength="medium",
        supports_validation=True,
    )

    snapshot = generator.generate(
        theme_id=THEME_ID,
        theme_name=THEME_NAME,
        policy_version=POLICY_VERSION,
        run_id="validation_progress_snapshot_004",
    )

    assert snapshot.current_state == "VALIDATING"
    assert snapshot.evidence_status == "EARLY_SUPPORTING_SIGNAL"
    assert snapshot.gate_status == "BLOCKED"
    assert snapshot.total_entries == 2
    assert snapshot.total_entries_needed == 3
    assert snapshot.primary_entries == 1
    assert snapshot.primary_entries_needed == 1
    assert snapshot.secondary_entries == 1
    assert snapshot.risk_entries == 0
    assert "primary evidence 1/2" in snapshot.gate_reason


def test_validation_progress_snapshot_ready_result_is_read_only():
    generator, registry, evidence_log = make_generator(
        registry_path=(
            "reports/intelligence/"
            "test_validation_progress_snapshot_ready_state_registry.json"
        ),
        evidence_log_path=(
            "reports/intelligence/"
            "test_validation_progress_snapshot_ready_evidence_log.json"
        ),
    )

    register_theme_as_validating(registry)
    add_ready_evidence(evidence_log)

    snapshot = generator.generate(
        theme_id=THEME_ID,
        theme_name=THEME_NAME,
        policy_version=POLICY_VERSION,
        run_id="validation_progress_snapshot_ready_001",
    )

    assert snapshot.gate_status == "READY_FOR_HUMAN_REVIEW"
    assert snapshot.evidence_status == "READY_FOR_HUMAN_REVIEW"
    assert snapshot.current_state == "VALIDATING"
    assert registry.get_current_state(THEME_ID) == "VALIDATING"

def test_validation_progress_snapshot_reports_already_ready_for_review():
    generator, registry, evidence_log = make_generator(
        registry_path=(
            "reports/intelligence/"
            "test_validation_progress_snapshot_already_ready_state_registry.json"
        ),
        evidence_log_path=(
            "reports/intelligence/"
            "test_validation_progress_snapshot_already_ready_evidence_log.json"
        ),
    )

    register_theme_as_validating(registry)
    add_ready_evidence(evidence_log)

    registry.transition(
        theme_id=THEME_ID,
        theme_name=THEME_NAME,
        new_state="READY_FOR_REVIEW",
        trigger="validation_gate_passed",
        reason="Validation evidence met human review threshold.",
        changed_by="ValidationGate",
        related_artifact_id="validation_progress_snapshot_001",
        policy_version=POLICY_VERSION,
        run_id="validation_progress_snapshot_already_ready_001",
    )

    snapshot = generator.generate(
        theme_id=THEME_ID,
        theme_name=THEME_NAME,
        policy_version=POLICY_VERSION,
        run_id="validation_progress_snapshot_already_ready_002",
    )

    assert snapshot.current_state == "READY_FOR_REVIEW"
    assert snapshot.evidence_status == "READY_FOR_HUMAN_REVIEW"
    assert snapshot.gate_status == "ALREADY_READY_FOR_REVIEW"
    assert "already passed the validation gate" in snapshot.gate_reason
    assert "human review packet" in snapshot.recommended_next_action


def test_validation_progress_snapshot_blocks_unregistered_theme():
    generator, _, _ = make_generator(
        registry_path=(
            "reports/intelligence/"
            "test_validation_progress_snapshot_missing_state_registry.json"
        ),
        evidence_log_path=(
            "reports/intelligence/"
            "test_validation_progress_snapshot_missing_evidence_log.json"
        ),
    )

    snapshot = generator.generate(
        theme_id=THEME_ID,
        theme_name=THEME_NAME,
        policy_version=POLICY_VERSION,
        run_id="validation_progress_snapshot_missing_001",
    )

    assert snapshot.current_state is None
    assert snapshot.gate_status == "BLOCKED"
    assert "not registered" in snapshot.gate_reason


def test_validation_progress_snapshot_formats_and_writes_markdown():
    generator, registry, evidence_log = make_generator(
        registry_path=(
            "reports/intelligence/"
            "test_validation_progress_snapshot_write_state_registry.json"
        ),
        evidence_log_path=(
            "reports/intelligence/"
            "test_validation_progress_snapshot_write_evidence_log.json"
        ),
    )

    register_theme_as_validating(registry)
    add_ready_evidence(evidence_log)

    snapshot = generator.generate(
        theme_id=THEME_ID,
        theme_name=THEME_NAME,
        policy_version=POLICY_VERSION,
        run_id="validation_progress_snapshot_write_001",
    )

    output_path = Path(
        "reports/intelligence/test_validation_progress_snapshots/"
        "lead_follow_up_progress_snapshot.md"
    )

    if output_path.exists():
        output_path.unlink()

    written_path = generator.write_markdown(
        snapshot=snapshot,
        output_path=output_path,
    )

    assert written_path.exists()

    content = written_path.read_text(encoding="utf-8")
    assert "Validation Progress Snapshot" in content
    assert "Gate Position" in content
    assert "read-only" in content


def test_validation_progress_snapshot_blocks_unsafe_output_path():
    generator, registry, evidence_log = make_generator(
        registry_path=(
            "reports/intelligence/"
            "test_validation_progress_snapshot_unsafe_state_registry.json"
        ),
        evidence_log_path=(
            "reports/intelligence/"
            "test_validation_progress_snapshot_unsafe_evidence_log.json"
        ),
    )

    register_theme_as_validating(registry)
    add_ready_evidence(evidence_log)

    snapshot = generator.generate(
        theme_id=THEME_ID,
        theme_name=THEME_NAME,
        policy_version=POLICY_VERSION,
        run_id="validation_progress_snapshot_unsafe_001",
    )

    with pytest.raises(ValidationProgressSnapshotError):
        generator.write_markdown(
            snapshot=snapshot,
            output_path="../../unsafe.md",
        )


def test_validation_progress_snapshot_reports_suspect_evidence_blocker():
    generator, registry, evidence_log = make_generator(
        registry_path=(
            "reports/intelligence/"
            "test_validation_progress_snapshot_suspect_state_registry.json"
        ),
        evidence_log_path=(
            "reports/intelligence/"
            "test_validation_progress_snapshot_suspect_evidence_log.json"
        ),
    )

    register_theme_as_validating(registry)

    for index in range(5):
        evidence_log.add_entry(
            theme=THEME_NAME,
            validation_plan_path=(
                "reports/intelligence/validation_plans/"
                "lead_and_follow_up_validation_plan.md"
            ),
            evidence_type="customer_interview",
            evidence_summary=f"Placeholder interview {index}",
            source_reference=f"manual_test_interview_{index}",
            signal_strength="strong",
            supports_validation=True,
            notes=(
                "Primary evidence placeholder. "
                "Replace with real interview reference."
            ),
        )

    snapshot = generator.generate(
        theme_id=THEME_ID,
        theme_name=THEME_NAME,
        policy_version=POLICY_VERSION,
        run_id="validation_progress_snapshot_suspect_001",
    )

    assert snapshot.evidence_status == "EVIDENCE_NEEDS_VERIFICATION"
    assert snapshot.gate_status == "BLOCKED"
    assert snapshot.total_entries == 5
    assert snapshot.gate_safe_entries == 0
    assert snapshot.gate_safe_primary_entries == 0
    assert snapshot.suspect_entries == 5
    assert "gate-safe evidence 0/5" in snapshot.gate_reason
    assert "suspect evidence 5" in snapshot.gate_reason
