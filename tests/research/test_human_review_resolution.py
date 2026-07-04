from datetime import UTC, datetime
from pathlib import Path
import shutil

import pytest

from src.hermes.human_review_decision import (
    HumanReviewDecisionError,
    HumanReviewResolutionService,
)
from src.hermes.human_review_packet import (
    HumanReviewPacket,
    HumanReviewPacketRegistry,
)
from src.hermes.theme_state_registry import ThemeStateRegistry
from src.hermes.validation_evidence_log import ValidationEvidenceLog
from src.hermes.validation_evidence_summary import (
    ValidationEvidenceSummarizer,
)


THEME_ID = "lead_follow_up_001"
THEME_NAME = "lead + follow up"
POLICY_VERSION = "2026-06-08.v1"
PLAN_PATH = (
    "reports/intelligence/validation_plans/"
    "lead_and_follow_up_validation_plan.md"
)


def runtime_paths(prefix: str) -> tuple[Path, Path, Path, Path]:
    root = Path("reports/intelligence")
    return (
        root / f"test_human_review_resolution_{prefix}_state.json",
        root / f"test_human_review_resolution_{prefix}_evidence.json",
        root / f"test_human_review_resolution_{prefix}_packets.json",
        root / f"test_human_review_resolution_{prefix}_packets",
    )


def clean_runtime_paths(prefix: str) -> None:
    for path in runtime_paths(prefix)[:3]:
        if path.exists():
            path.unlink()

    packet_dir = runtime_paths(prefix)[3]
    if packet_dir.exists():
        shutil.rmtree(packet_dir)


def register_review_ready_theme(registry: ThemeStateRegistry) -> None:
    registry.register_theme(
        theme_id=THEME_ID,
        theme_name=THEME_NAME,
        trigger="trend_detected",
        reason="Repeated lead follow-up pain found.",
        changed_by="HermesMemoryTrendDetector",
        related_artifact_id="trend_report_001",
        policy_version=POLICY_VERSION,
        run_id="human_review_resolution_001",
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
        run_id="human_review_resolution_002",
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
        run_id="human_review_resolution_003",
    )
    registry.transition(
        theme_id=THEME_ID,
        theme_name=THEME_NAME,
        new_state="READY_FOR_REVIEW",
        trigger="validation_gate_passed",
        reason="Validation evidence met human review threshold.",
        changed_by="ValidationGate",
        related_artifact_id="validation_summary_001",
        policy_version=POLICY_VERSION,
        run_id="human_review_resolution_004",
    )


def add_review_ready_evidence(log: ValidationEvidenceLog) -> None:
    for index in range(5):
        log.add_entry(
            theme=THEME_NAME,
            validation_plan_path=PLAN_PATH,
            evidence_type="customer_interview",
            evidence_summary=(
                "Business owner confirmed delayed enquiry follow-up can "
                "lose bookings."
            ),
            source_reference=f"interview_{index + 1}",
            signal_strength="strong" if index < 3 else "medium",
            supports_validation=True,
            source_trust=ValidationEvidenceLog.HUMAN_ATTESTED_FIRST_PARTY,
            notes="Primary first-party record.",
        )


def create_registered_packet(
    *,
    registry: ThemeStateRegistry,
    log: ValidationEvidenceLog,
    packet_registry: HumanReviewPacketRegistry,
    packet_dir: Path,
    prefix: str,
) -> tuple[str, Path]:
    summary = ValidationEvidenceSummarizer(log).summarize_theme(THEME_NAME)
    latest_event = registry.list_events_for_theme(THEME_ID)[-1]
    packet_id = f"human_review_packet_{prefix}_001"
    packet_path = packet_dir / f"{prefix}_packet.md"
    packet_dir.mkdir(parents=True, exist_ok=True)

    packet = HumanReviewPacket(
        packet_id=packet_id,
        theme_id=THEME_ID,
        theme_name=THEME_NAME,
        current_state="READY_FOR_REVIEW",
        review_status="PENDING_HUMAN_DECISION",
        validation_plan_path=PLAN_PATH,
        validation_plan_status="REGISTERED",
        validation_plan_timestamp=datetime.now(UTC).isoformat(),
        gate_event_id=latest_event.event_id,
        gate_run_id=latest_event.run_id,
        gate_policy_version=POLICY_VERSION,
        state_history=registry.list_events_for_theme(THEME_ID),
        evidence_summary=summary,
        gate_safe_evidence=log.list_entries_for_theme(THEME_NAME),
        excluded_evidence=[],
        risk_evidence=[],
        opposing_evidence=[],
        reasons_not_to_build=[],
        policy_version=POLICY_VERSION,
        run_id=f"human_review_packet_{prefix}_001",
        timestamp=datetime.now(UTC).isoformat(),
    )

    packet_path.write_text(
        "\n".join(
            [
                f"# Human Review Packet: {THEME_NAME}",
                f"- Packet ID: {packet_id}",
                f"- Theme ID: {THEME_ID}",
                f"- Theme Name: {THEME_NAME}",
                "- Current State: READY_FOR_REVIEW",
                "- Evidence Status: READY_FOR_HUMAN_REVIEW",
                f"- Gate Event ID: {latest_event.event_id}",
                f"- Gate Policy Version: {POLICY_VERSION}",
            ]
        ),
        encoding="utf-8",
    )
    packet_registry.add_packet(packet=packet, output_path=packet_path)
    return packet_id, packet_path


def make_components(prefix: str):
    clean_runtime_paths(prefix)
    state_path, evidence_path, packet_index_path, packet_dir = runtime_paths(prefix)
    registry = ThemeStateRegistry(registry_path=state_path)
    log = ValidationEvidenceLog(log_path=evidence_path)
    packet_registry = HumanReviewPacketRegistry(
        registry_path=packet_index_path,
        packet_output_dir=packet_dir,
    )
    service = HumanReviewResolutionService(
        state_registry=registry,
        evidence_summarizer=ValidationEvidenceSummarizer(log),
        packet_registry=packet_registry,
    )
    return service, registry, log, packet_registry, packet_dir


def prepare_ready_resolution(prefix: str):
    service, registry, log, packet_registry, packet_dir = make_components(prefix)
    register_review_ready_theme(registry)
    add_review_ready_evidence(log)
    packet_id, packet_path = create_registered_packet(
        registry=registry,
        log=log,
        packet_registry=packet_registry,
        packet_dir=packet_dir,
        prefix=prefix,
    )
    return service, registry, log, packet_id, packet_path


def test_human_review_resolution_approves_mvp_planning_with_registered_packet():
    service, registry, log, packet_id, _ = prepare_ready_resolution("approve")
    state_count_before = len(registry.list_events_for_theme(THEME_ID))
    evidence_count_before = len(log.list_entries_for_theme(THEME_NAME))

    result = service.resolve(
        theme_id=THEME_ID,
        theme_name=THEME_NAME,
        decision="approve_mvp_planning",
        reviewer_reference="reviewer_001",
        decision_reason="Evidence and review packet support controlled planning.",
        review_packet_id=packet_id,
        policy_version=POLICY_VERSION,
        run_id="human_review_resolution_approve_001",
    )

    assert result.decision == "APPROVE_MVP_PLANNING"
    assert result.previous_state == "READY_FOR_REVIEW"
    assert result.new_state == "MVP_PLANNING"
    assert registry.get_current_state(THEME_ID) == "MVP_PLANNING"
    assert len(registry.list_events_for_theme(THEME_ID)) == state_count_before + 1
    assert len(log.list_entries_for_theme(THEME_NAME)) == evidence_count_before

    latest_event = registry.list_events_for_theme(THEME_ID)[-1]
    assert latest_event.trigger == ThemeStateRegistry.HUMAN_REVIEW_APPROVE_TRIGGER
    assert latest_event.changed_by == ThemeStateRegistry.HUMAN_REVIEW_RETURN_ACTOR
    assert packet_id in latest_event.reason
    registry.verify_integrity()


def test_human_review_resolution_rejects_with_registered_packet():
    service, registry, _, packet_id, _ = prepare_ready_resolution("reject")

    result = service.resolve(
        theme_id=THEME_ID,
        theme_name=THEME_NAME,
        decision="reject",
        reviewer_reference="reviewer_001",
        decision_reason="Human review rejected the opportunity after review.",
        review_packet_id=packet_id,
        policy_version=POLICY_VERSION,
        run_id="human_review_resolution_reject_001",
    )

    assert result.decision == "REJECT"
    assert result.new_state == "REJECTED"
    assert registry.get_current_state(THEME_ID) == "REJECTED"
    assert registry.list_events_for_theme(THEME_ID)[-1].trigger == (
        ThemeStateRegistry.HUMAN_REVIEW_REJECT_TRIGGER
    )


def test_human_review_resolution_blocks_tampered_packet_content():
    service, _, _, packet_id, packet_path = prepare_ready_resolution("tampered")
    packet_path.write_text("# Altered packet\n", encoding="utf-8")

    with pytest.raises(
        HumanReviewDecisionError,
        match="does not match its registered provenance",
    ):
        service.resolve(
            theme_id=THEME_ID,
            theme_name=THEME_NAME,
            decision="approve_mvp_planning",
            reviewer_reference="reviewer_001",
            decision_reason="Attempt to approve with altered packet.",
            review_packet_id=packet_id,
            policy_version=POLICY_VERSION,
            run_id="human_review_resolution_tampered_001",
        )


def test_human_review_resolution_blocks_invalid_reviewer_reference():
    service, _, _, packet_id, _ = prepare_ready_resolution("reviewer")

    with pytest.raises(HumanReviewDecisionError, match="letters, numbers"):
        service.resolve(
            theme_id=THEME_ID,
            theme_name=THEME_NAME,
            decision="approve_mvp_planning",
            reviewer_reference="reviewer@example.com",
            decision_reason="Attempt to approve with personal data in the reference.",
            review_packet_id=packet_id,
            policy_version=POLICY_VERSION,
            run_id="human_review_resolution_reviewer_001",
        )


def test_human_review_resolution_blocks_unknown_packet():
    service, _, _, _, _ = prepare_ready_resolution("missing_packet")

    with pytest.raises(HumanReviewDecisionError, match="not registered"):
        service.resolve(
            theme_id=THEME_ID,
            theme_name=THEME_NAME,
            decision="reject",
            reviewer_reference="reviewer_001",
            decision_reason="Reject with unknown packet should be blocked.",
            review_packet_id="human_review_packet_missing_001",
            policy_version=POLICY_VERSION,
            run_id="human_review_resolution_missing_packet_001",
        )
