import subprocess
from pathlib import Path

from src.hermes.human_review_packet import (
    HumanReviewPacket,
    HumanReviewPacketRegistry,
)
from src.hermes.theme_state_registry import ThemeStateRegistry
from src.hermes.validation_evidence_log import ValidationEvidenceLog
from src.hermes.validation_evidence_summary import (
    ValidationEvidenceSummarizer,
)


SCRIPT = "scripts/resolve_human_review.py"
THEME_ID = "lead_follow_up_001"
THEME_NAME = "lead + follow up"
POLICY_VERSION = "2026-06-08.v1"
PLAN_PATH = (
    "reports/intelligence/validation_plans/"
    "lead_and_follow_up_validation_plan.md"
)

STATE_PATH = Path("reports/intelligence/test_resolve_human_review_cli_state.json")
EVIDENCE_PATH = Path("reports/intelligence/test_resolve_human_review_cli_evidence.json")
PACKET_INDEX_PATH = Path("reports/intelligence/test_resolve_human_review_cli_packets.json")
PACKET_DIR = Path("reports/intelligence/test_resolve_human_review_cli_packets")
PACKET_PATH = PACKET_DIR / "review_packet.md"
PACKET_ID = "human_review_packet_cli_001"


def clean_runtime_files() -> None:
    for path in [STATE_PATH, EVIDENCE_PATH, PACKET_INDEX_PATH, PACKET_PATH]:
        if path.exists():
            path.unlink()
    PACKET_DIR.mkdir(parents=True, exist_ok=True)


def prepare_review_ready_resolution() -> None:
    registry = ThemeStateRegistry(registry_path=STATE_PATH)
    log = ValidationEvidenceLog(log_path=EVIDENCE_PATH)
    packet_registry = HumanReviewPacketRegistry(
        registry_path=PACKET_INDEX_PATH,
        packet_output_dir=PACKET_DIR,
    )

    registry.register_theme(
        theme_id=THEME_ID,
        theme_name=THEME_NAME,
        trigger="trend_detected",
        reason="Repeated lead follow-up pain found.",
        changed_by="HermesMemoryTrendDetector",
        related_artifact_id="trend_report_001",
        policy_version=POLICY_VERSION,
        run_id="resolve_cli_001",
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
        run_id="resolve_cli_002",
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
        run_id="resolve_cli_003",
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
        run_id="resolve_cli_004",
    )

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

    latest_event = registry.list_events_for_theme(THEME_ID)[-1]
    summary = ValidationEvidenceSummarizer(log).summarize_theme(THEME_NAME)
    packet = HumanReviewPacket(
        packet_id=PACKET_ID,
        theme_id=THEME_ID,
        theme_name=THEME_NAME,
        current_state="READY_FOR_REVIEW",
        review_status="PENDING_HUMAN_DECISION",
        validation_plan_path=PLAN_PATH,
        validation_plan_status="REGISTERED",
        validation_plan_timestamp="2026-06-28T00:00:00+00:00",
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
        run_id="resolve_cli_packet_001",
        timestamp="2026-06-28T00:00:00+00:00",
    )
    PACKET_PATH.write_text(
        "\n".join(
            [
                f"# Human Review Packet: {THEME_NAME}",
                f"- Packet ID: {PACKET_ID}",
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
    packet_registry.add_packet(packet=packet, output_path=PACKET_PATH)


def test_resolve_human_review_cli_approves_mvp_planning():
    clean_runtime_files()
    prepare_review_ready_resolution()

    result = subprocess.run(
        [
            "python",
            SCRIPT,
            "--theme-id",
            THEME_ID,
            "--theme-name",
            THEME_NAME,
            "--decision",
            "approve_mvp_planning",
            "--reviewer-reference",
            "reviewer_001",
            "--decision-reason",
            "Human review approved controlled planning.",
            "--review-packet-id",
            PACKET_ID,
            "--policy-version",
            POLICY_VERSION,
            "--run-id",
            "resolve_cli_success_001",
            "--state-registry-path",
            str(STATE_PATH),
            "--evidence-log-path",
            str(EVIDENCE_PATH),
            "--packet-registry-path",
            str(PACKET_INDEX_PATH),
            "--packet-output-dir",
            str(PACKET_DIR),
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    assert "Human Review Resolution Recorded" in result.stdout
    assert "Decision: APPROVE_MVP_PLANNING" in result.stdout
    assert "New State: MVP_PLANNING" in result.stdout

    registry = ThemeStateRegistry(registry_path=STATE_PATH)
    assert registry.get_current_state(THEME_ID) == "MVP_PLANNING"


def test_resolve_human_review_cli_blocks_missing_packet():
    clean_runtime_files()
    prepare_review_ready_resolution()

    result = subprocess.run(
        [
            "python",
            SCRIPT,
            "--theme-id",
            THEME_ID,
            "--theme-name",
            THEME_NAME,
            "--decision",
            "reject",
            "--reviewer-reference",
            "reviewer_001",
            "--decision-reason",
            "Attempt with missing packet.",
            "--review-packet-id",
            "human_review_packet_missing_001",
            "--policy-version",
            POLICY_VERSION,
            "--run-id",
            "resolve_cli_missing_001",
            "--state-registry-path",
            str(STATE_PATH),
            "--evidence-log-path",
            str(EVIDENCE_PATH),
            "--packet-registry-path",
            str(PACKET_INDEX_PATH),
            "--packet-output-dir",
            str(PACKET_DIR),
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 1
    assert "Human review resolution blocked" in result.stderr
    assert "not registered" in result.stderr

    registry = ThemeStateRegistry(registry_path=STATE_PATH)
    assert registry.get_current_state(THEME_ID) == "READY_FOR_REVIEW"



def test_resolve_human_review_cli_blocks_unsafe_packet_registry_path():
    clean_runtime_files()
    prepare_review_ready_resolution()

    result = subprocess.run(
        [
            "python",
            SCRIPT,
            "--theme-id",
            THEME_ID,
            "--theme-name",
            THEME_NAME,
            "--decision",
            "reject",
            "--reviewer-reference",
            "reviewer_001",
            "--decision-reason",
            "Attempt with unsafe packet registry path.",
            "--review-packet-id",
            PACKET_ID,
            "--policy-version",
            POLICY_VERSION,
            "--run-id",
            "resolve_cli_unsafe_registry_001",
            "--state-registry-path",
            str(STATE_PATH),
            "--evidence-log-path",
            str(EVIDENCE_PATH),
            "--packet-registry-path",
            "../../unsafe_packet_registry.json",
            "--packet-output-dir",
            str(PACKET_DIR),
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 1
    assert "Human review resolution blocked" in result.stderr
    assert "reports/intelligence" in result.stderr

    registry = ThemeStateRegistry(registry_path=STATE_PATH)
    assert registry.get_current_state(THEME_ID) == "READY_FOR_REVIEW"
