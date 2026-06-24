import subprocess
from pathlib import Path

from src.hermes.theme_state_registry import ThemeStateRegistry
from src.hermes.validation_evidence_log import ValidationEvidenceLog


SCRIPT = "scripts/run_validation_gate.py"
THEME_ID = "lead_follow_up_001"
THEME_NAME = "lead + follow up"
POLICY_VERSION = "2026-06-08.v1"

STATE_REGISTRY_PATH = Path("reports/intelligence/test_run_validation_gate_state_registry.json")
EVIDENCE_LOG_PATH = Path("reports/intelligence/test_run_validation_gate_evidence_log.json")

def clean_runtime_files() -> None:
    for path in [STATE_REGISTRY_PATH, EVIDENCE_LOG_PATH]:
        if path.exists():
            path.unlink()


def register_theme_as_validating() -> None:
    registry = ThemeStateRegistry(registry_path=STATE_REGISTRY_PATH)

    registry.register_theme(
        theme_id=THEME_ID,
        theme_name=THEME_NAME,
        trigger="trend_detected",
        reason="Repeated lead follow-up pain found.",
        changed_by="test",
        related_artifact_id="trend_report_001",
        policy_version=POLICY_VERSION,
        run_id="validation_gate_cli_test_001",
    )

    registry.transition(
        theme_id=THEME_ID,
        theme_name=THEME_NAME,
        new_state="VALIDATION_READY",
        trigger="validation_readiness_passed",
        reason="Theme met validation readiness criteria.",
        changed_by="test",
        related_artifact_id="readiness_report_001",
        policy_version=POLICY_VERSION,
        run_id="validation_gate_cli_test_002",
    )

    registry.transition(
        theme_id=THEME_ID,
        theme_name=THEME_NAME,
        new_state="VALIDATING",
        trigger="validation_plan_created",
        reason="Validation plan created.",
        changed_by="test",
        related_artifact_id="validation_plan_001",
        policy_version=POLICY_VERSION,
        run_id="validation_gate_cli_test_003",
    )


def add_ready_evidence() -> None:
    log = ValidationEvidenceLog(log_path=EVIDENCE_LOG_PATH)

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
            source_trust=ValidationEvidenceLog.HUMAN_ATTESTED_FIRST_PARTY,
        )


def test_run_validation_gate_cli_blocks_when_evidence_is_not_ready():
    clean_runtime_files()
    register_theme_as_validating()

    result = subprocess.run(
        [
            "python",
            SCRIPT,
            "--theme-id",
            THEME_ID,
            "--theme-name",
            THEME_NAME,
            "--state-registry-path",
            str(STATE_REGISTRY_PATH),
            "--evidence-log-path",
            str(EVIDENCE_LOG_PATH),
            "--policy-version",
            POLICY_VERSION,
            "--run-id",
            "validation_gate_cli_blocked",
            "--related-artifact-id",
            "validation_summary_test",
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 1
    assert "Validation Gate Result" in result.stdout
    assert "Gate Status: BLOCKED" in result.stdout
    assert "Evidence Status: NO_EVIDENCE" in result.stdout


def test_run_validation_gate_cli_moves_ready_theme_to_human_review():
    clean_runtime_files()
    register_theme_as_validating()
    add_ready_evidence()

    plan_path = Path(
        "reports/intelligence/validation_plans/"
        "lead_and_follow_up_validation_plan.md"
    )
    plan_path.parent.mkdir(parents=True, exist_ok=True)
    plan_path.write_text("# Test validation plan", encoding="utf-8")

    result = subprocess.run(
        [
            "python",
            SCRIPT,
            "--theme-id",
            THEME_ID,
            "--theme-name",
            THEME_NAME,
            "--state-registry-path",
            str(STATE_REGISTRY_PATH),
            "--evidence-log-path",
            str(EVIDENCE_LOG_PATH),
            "--policy-version",
            POLICY_VERSION,
            "--run-id",
            "validation_gate_cli_passed",
            "--related-artifact-id",
            "validation_summary_test",
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    assert "Validation Gate Result" in result.stdout
    assert "Gate Status: READY_FOR_HUMAN_REVIEW" in result.stdout
    assert "State Changed: True" in result.stdout
