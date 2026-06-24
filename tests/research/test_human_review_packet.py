from pathlib import Path

import pytest

from src.hermes.human_review_packet import (
    HumanReviewPacketError,
    HumanReviewPacketGenerator,
    HumanReviewPacketRegistry,
)
from src.hermes.theme_state_registry import ThemeStateRegistry
from src.hermes.theme_validation_plan import ThemeValidationPlan
from src.hermes.theme_validation_plan_registry import (
    ThemeValidationPlanRegistry,
)
from src.hermes.validation_evidence_log import ValidationEvidenceLog
from src.hermes.validation_evidence_summary import (
    ValidationEvidenceSummarizer,
)
from src.hermes.validation_gate import ValidationGate


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
    HumanReviewPacketGenerator,
    HumanReviewPacketRegistry,
    ThemeStateRegistry,
    ThemeValidationPlanRegistry,
    ValidationEvidenceLog,
]:
    state_path = (
        f"reports/intelligence/"
        f"test_human_review_packet_{prefix}_state_registry.json"
    )
    plan_index_path = (
        f"reports/intelligence/"
        f"test_human_review_packet_{prefix}_plan_index.json"
    )
    evidence_path = (
        f"reports/intelligence/"
        f"test_human_review_packet_{prefix}_evidence_log.json"
    )
    packet_index_path = (
        f"reports/intelligence/"
        f"test_human_review_packet_{prefix}_packet_index.json"
    )

    for path in [
        state_path,
        plan_index_path,
        evidence_path,
        packet_index_path,
    ]:
        clean_path(path)

    state_registry = ThemeStateRegistry(registry_path=state_path)
    plan_registry = ThemeValidationPlanRegistry(
        registry_path=plan_index_path,
    )
    evidence_log = ValidationEvidenceLog(log_path=evidence_path)

    generator = HumanReviewPacketGenerator(
        state_registry=state_registry,
        validation_plan_registry=plan_registry,
        evidence_log=evidence_log,
    )

    packet_registry = HumanReviewPacketRegistry(
        registry_path=packet_index_path,
    )

    return (
        generator,
        packet_registry,
        state_registry,
        plan_registry,
        evidence_log,
    )


def register_theme_as_validating(registry: ThemeStateRegistry) -> None:
    registry.register_theme(
        theme_id=THEME_ID,
        theme_name=THEME_NAME,
        trigger="trend_detected",
        reason="Repeated lead follow-up pain found.",
        changed_by="HermesMemoryTrendDetector",
        related_artifact_id="trend_report_001",
        policy_version=POLICY_VERSION,
        run_id="human_review_packet_001",
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
        run_id="human_review_packet_002",
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
        run_id="human_review_packet_003",
    )


def create_and_register_plan(
    registry: ThemeValidationPlanRegistry,
    *,
    prefix: str,
) -> str:
    plan_path = Path(
        "reports/intelligence/test_human_review_packet_plans/"
        f"{prefix}_lead_and_follow_up_validation_plan.md"
    )

    plan_path.parent.mkdir(parents=True, exist_ok=True)
    plan_path.write_text(
        "# Test Validation Plan\n\nValidation plan fixture.",
        encoding="utf-8",
    )

    plan = ThemeValidationPlan(
        theme=THEME_NAME,
        readiness="VALIDATION_READY",
        readiness_score=68.27,
        output_path=str(plan_path),
        validation_goal="Validate lead follow-up pain.",
        target_users=["Small service business owners"],
        hypotheses=["Manual follow-up causes lost leads."],
        validation_methods=["Customer interviews"],
        success_criteria=["Users confirm weekly pain."],
        failure_criteria=["No willingness to pay."],
        evidence_to_collect=["Interview notes"],
        risks_to_check=["CRM integration complexity"],
        recommended_next_action="Validate before MVP planning.",
    )

    registry.add_plan(plan)

    return str(plan_path)


def add_ready_evidence(
    log: ValidationEvidenceLog,
    *,
    validation_plan_path: str,
) -> None:
    for index in range(5):
        log.add_entry(
            theme=THEME_NAME,
            validation_plan_path=validation_plan_path,
            evidence_type="customer_interview",
            evidence_summary=(
                "Owner confirmed that delayed lead follow-up can lose "
                "bookings and sales."
            ),
            source_reference=f"interview_{index + 1}",
            signal_strength="strong" if index < 3 else "medium",
            supports_validation=True,
            notes="Primary customer interview evidence.",
            source_trust=ValidationEvidenceLog.HUMAN_ATTESTED_FIRST_PARTY,
        )


def pass_validation_gate(
    registry: ThemeStateRegistry,
    evidence_log: ValidationEvidenceLog,
) -> None:
    gate = ValidationGate(
        state_registry=registry,
        evidence_summarizer=ValidationEvidenceSummarizer(evidence_log),
    )

    result = gate.evaluate(
        theme_id=THEME_ID,
        theme_name=THEME_NAME,
        policy_version=POLICY_VERSION,
        run_id="human_review_packet_gate_001",
        related_artifact_id="validation_evidence_summary_001",
    )

    assert result.state_changed is True
    assert result.new_state == "READY_FOR_REVIEW"


def prepare_ready_packet(prefix: str):
    (
        generator,
        packet_registry,
        state_registry,
        plan_registry,
        evidence_log,
    ) = make_components(prefix)

    validation_plan_path = create_and_register_plan(
        plan_registry,
        prefix=prefix,
    )

    register_theme_as_validating(state_registry)

    add_ready_evidence(
        evidence_log,
        validation_plan_path=validation_plan_path,
    )

    pass_validation_gate(state_registry, evidence_log)

    return (
        generator,
        packet_registry,
        state_registry,
        evidence_log,
        validation_plan_path,
    )


def test_human_review_packet_generates_and_registers_without_state_change():
    (
        generator,
        packet_registry,
        state_registry,
        evidence_log,
        _,
    ) = prepare_ready_packet("success")

    state_event_count_before = len(
        state_registry.list_events_for_theme(THEME_ID)
    )
    evidence_count_before = len(
        evidence_log.list_entries_for_theme(THEME_NAME)
    )

    packet = generator.generate(
        theme_id=THEME_ID,
        theme_name=THEME_NAME,
        policy_version=POLICY_VERSION,
        run_id="human_review_packet_success_001",
    )

    output_path = generator.default_output_path(packet)

    written_path = generator.write_markdown(
        packet=packet,
        output_path=output_path,
    )

    registry_entry = packet_registry.add_packet(
        packet=packet,
        output_path=written_path,
    )

    assert packet.current_state == "READY_FOR_REVIEW"
    assert packet.review_status == "PENDING_HUMAN_DECISION"
    assert packet.evidence_summary.status == "READY_FOR_HUMAN_REVIEW"
    assert len(packet.gate_safe_evidence) == 5
    assert packet.excluded_evidence == []
    assert registry_entry.packet_id == packet.packet_id
    assert written_path.exists()

    assert len(state_registry.list_events_for_theme(THEME_ID)) == (
        state_event_count_before
    )
    assert len(evidence_log.list_entries_for_theme(THEME_NAME)) == (
        evidence_count_before
    )

    content = written_path.read_text(encoding="utf-8")

    assert "Human Review Packet" in content
    assert "Human Decision Record" in content
    assert "does not approve building" in content


def test_human_review_packet_separates_excluded_evidence_from_gate_safe_evidence():
    (
        generator,
        _,
        state_registry,
        evidence_log,
        validation_plan_path,
    ) = prepare_ready_packet("excluded")

    evidence_log.add_entry(
        theme=THEME_NAME,
        validation_plan_path=validation_plan_path,
        evidence_type="customer_interview",
        evidence_summary=(
            "Participant/Signal: small_business_owner_003. "
            "Finding: REPLACE_WITH_REAL_FINDING"
        ),
        source_reference="interview_template_001",
        signal_strength="strong",
        supports_validation=True,
        notes="Primary customer interview evidence.",
        source_trust=ValidationEvidenceLog.HUMAN_ATTESTED_FIRST_PARTY,
    )

    evidence_log.add_entry(
        theme=THEME_NAME,
        validation_plan_path=validation_plan_path,
        evidence_type="competitor_check",
        evidence_summary=(
            "Competitor: COMPETITOR_NAME_HERE. Finding: "
            "Describe what the competitor offers, where it is too broad."
        ),
        source_reference="competitor_template_001",
        signal_strength="medium",
        supports_validation=True,
        notes="Secondary competitor evidence.",
        source_trust=ValidationEvidenceLog.PUBLIC_COMPETITOR,
    )

    gate = ValidationGate(
        state_registry=state_registry,
        evidence_summarizer=ValidationEvidenceSummarizer(evidence_log),
    )

    assert state_registry.get_current_state(THEME_ID) == "READY_FOR_REVIEW"

    packet = generator.generate(
        theme_id=THEME_ID,
        theme_name=THEME_NAME,
        policy_version=POLICY_VERSION,
        run_id="human_review_packet_excluded_001",
    )

    markdown = generator.format_markdown(packet)

    assert len(packet.gate_safe_evidence) == 5
    assert len(packet.excluded_evidence) == 2

    excluded_sources = {
        finding.source_reference
        for finding in packet.excluded_evidence
    }

    assert excluded_sources == {
        "interview_template_001",
        "competitor_template_001",
    }


def test_human_review_packet_blocks_before_validation_gate_transition():
    (
        generator,
        _,
        state_registry,
        plan_registry,
        evidence_log,
    ) = make_components("not_ready")

    validation_plan_path = create_and_register_plan(
        plan_registry,
        prefix="not_ready",
    )

    register_theme_as_validating(state_registry)

    add_ready_evidence(
        evidence_log,
        validation_plan_path=validation_plan_path,
    )

    with pytest.raises(
        HumanReviewPacketError,
        match="READY_FOR_REVIEW",
    ):
        generator.generate(
            theme_id=THEME_ID,
            theme_name=THEME_NAME,
            policy_version=POLICY_VERSION,
            run_id="human_review_packet_not_ready_001",
        )

def test_human_review_packet_blocks_legacy_ready_state_after_template_reclassification():
    (
        generator,
        _,
        state_registry,
        plan_registry,
        evidence_log,
    ) = make_components("legacy_reclassification")

    validation_plan_path = create_and_register_plan(
        plan_registry,
        prefix="legacy_reclassification",
    )

    register_theme_as_validating(state_registry)

    for index in range(5):
        evidence_log.add_entry(
            theme=THEME_NAME,
            validation_plan_path=validation_plan_path,
            evidence_type="customer_interview",
            evidence_summary=(
                "Participant/Signal: small_business_owner_003. "
                "Finding: REPLACE_WITH_REAL_FINDING"
            ),
            source_reference=f"legacy_interview_{index}",
            signal_strength="strong",
            supports_validation=True,
            notes="Primary customer interview evidence.",
            source_trust=ValidationEvidenceLog.HUMAN_ATTESTED_FIRST_PARTY,
        )

    state_registry.transition(
        theme_id=THEME_ID,
        theme_name=THEME_NAME,
        new_state="READY_FOR_REVIEW",
        trigger="validation_gate_passed",
        reason="Legacy gate event created before template detection was hardened.",
        changed_by="ValidationGate",
        related_artifact_id="validation_summary_001",
        policy_version=POLICY_VERSION,
        run_id="human_review_packet_legacy_reclassification_001",
    )

    with pytest.raises(
        HumanReviewPacketError,
        match="EVIDENCE_NEEDS_VERIFICATION",
    ):
        generator.generate(
            theme_id=THEME_ID,
            theme_name=THEME_NAME,
            policy_version=POLICY_VERSION,
            run_id="human_review_packet_legacy_reclassification_002",
        )

def test_human_review_packet_blocks_unregistered_evidence_plan_reference():
    (
        generator,
        _,
        state_registry,
        plan_registry,
        evidence_log,
    ) = make_components("unregistered_plan")

    create_and_register_plan(
        plan_registry,
        prefix="unregistered_plan_registered",
    )

    unregistered_plan_path = Path(
        "reports/intelligence/test_human_review_packet_plans/"
        "unregistered_plan_reference.md"
    )
    unregistered_plan_path.parent.mkdir(parents=True, exist_ok=True)
    unregistered_plan_path.write_text(
        "# Unregistered Plan\n",
        encoding="utf-8",
    )

    register_theme_as_validating(state_registry)

    add_ready_evidence(
        evidence_log,
        validation_plan_path=str(unregistered_plan_path),
    )

    pass_validation_gate(state_registry, evidence_log)

    with pytest.raises(
        HumanReviewPacketError,
        match="not registered",
    ):
        generator.generate(
            theme_id=THEME_ID,
            theme_name=THEME_NAME,
            policy_version=POLICY_VERSION,
            run_id="human_review_packet_unregistered_plan_001",
        )


def test_human_review_packet_blocks_unsafe_output_path():
    (
        generator,
        _,
        _,
        _,
        _,
    ) = prepare_ready_packet("unsafe_output")

    packet = generator.generate(
        theme_id=THEME_ID,
        theme_name=THEME_NAME,
        policy_version=POLICY_VERSION,
        run_id="human_review_packet_unsafe_output_001",
    )

    with pytest.raises(HumanReviewPacketError):
        generator.write_markdown(
            packet=packet,
            output_path="../../unsafe.md",
        )


def test_human_review_packet_blocks_non_markdown_output_path():
    (
        generator,
        _,
        _,
        _,
        _,
    ) = prepare_ready_packet("non_markdown")

    packet = generator.generate(
        theme_id=THEME_ID,
        theme_name=THEME_NAME,
        policy_version=POLICY_VERSION,
        run_id="human_review_packet_non_markdown_001",
    )

    with pytest.raises(HumanReviewPacketError):
        generator.write_markdown(
            packet=packet,
            output_path=(
                "reports/intelligence/human_review_packets/"
                "invalid_packet.txt"
            ),
        )


def test_human_review_packet_blocks_tampered_state_registry():
    (
        generator,
        _,
        state_registry,
        _,
        _,
    ) = prepare_ready_packet("tampered_registry")

    registry_path = Path(state_registry.registry_path)
    content = registry_path.read_text(encoding="utf-8")

    registry_path.write_text(
        content.replace("ValidationGate", "TamperedGate", 1),
        encoding="utf-8",
    )

    with pytest.raises(
        HumanReviewPacketError,
        match="integrity",
    ):
        generator.generate(
            theme_id=THEME_ID,
            theme_name=THEME_NAME,
            policy_version=POLICY_VERSION,
            run_id="human_review_packet_tampered_registry_001",
        )
