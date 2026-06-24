import subprocess
from pathlib import Path

from src.hermes.theme_state_registry import ThemeStateRegistry
from src.hermes.validation_evidence_log import ValidationEvidenceLog


SCRIPT = "scripts/return_theme_to_validation.py"

THEME_ID = "lead_follow_up_001"
THEME_NAME = "lead + follow up"
POLICY_VERSION = "2026-06-08.v1"

STATE_PATH = Path(
    "reports/intelligence/test_return_theme_to_validation_state_registry.json"
)
EVIDENCE_PATH = Path(
    "reports/intelligence/test_return_theme_to_validation_evidence_log.json"
)
CONTEXT_PATH = Path(
    "reports/intelligence/test_human_review_decision_contexts/"
    "cli_context.md"
)


def clean_runtime_files() -> None:
    for path in [STATE_PATH, EVIDENCE_PATH]:
        if path.exists():
            path.unlink()

    CONTEXT_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONTEXT_PATH.write_text(
        "# Evidence Repair Context\n",
        encoding="utf-8",
    )


def register_theme_as_ready_for_review() -> None:
    registry = ThemeStateRegistry(registry_path=STATE_PATH)

    registry.register_theme(
        theme_id=THEME_ID,
        theme_name=THEME_NAME,
        trigger="trend_detected",
        reason="Repeated lead follow-up pain found.",
        changed_by="HermesMemoryTrendDetector",
        related_artifact_id="trend_report_001",
        policy_version=POLICY_VERSION,
        run_id="return_cli_001",
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
        run_id="return_cli_002",
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
        run_id="return_cli_003",
    )

    registry.transition(
        theme_id=THEME_ID,
        theme_name=THEME_NAME,
        new_state="READY_FOR_REVIEW",
        trigger="validation_gate_passed",
        reason="Legacy gate event created before evidence repair.",
        changed_by="ValidationGate",
        related_artifact_id="validation_progress_snapshot_001",
        policy_version=POLICY_VERSION,
        run_id="return_cli_004",
    )


def add_template_evidence() -> None:
    log = ValidationEvidenceLog(log_path=EVIDENCE_PATH)

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
            source_trust=ValidationEvidenceLog.HUMAN_ATTESTED_FIRST_PARTY,
        )


def test_return_theme_to_validation_cli_records_controlled_return():
    clean_runtime_files()
    register_theme_as_ready_for_review()
    add_template_evidence()

    result = subprocess.run(
        [
            "python",
            SCRIPT,
            "--theme-id",
            THEME_ID,
            "--theme-name",
            THEME_NAME,
            "--reviewer-reference",
            "reviewer_001",
            "--decision-reason",
            "Template evidence was reclassified and needs replacement.",
            "--review-context-path",
            str(CONTEXT_PATH),
            "--policy-version",
            POLICY_VERSION,
            "--run-id",
            "return_cli_success_001",
            "--state-registry-path",
            str(STATE_PATH),
            "--evidence-log-path",
            str(EVIDENCE_PATH),
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    assert "Human Review Return Recorded" in result.stdout
    assert "New State: VALIDATING" in result.stdout
    assert "Decision Status: RETURNED_TO_VALIDATION" in result.stdout

    registry = ThemeStateRegistry(registry_path=STATE_PATH)
    assert registry.get_current_state(THEME_ID) == "VALIDATING"


def test_return_theme_to_validation_cli_blocks_missing_context_file():
    clean_runtime_files()
    register_theme_as_ready_for_review()
    add_template_evidence()

    missing_context = (
        "reports/intelligence/"
        "test_human_review_decision_contexts/does_not_exist.md"
    )

    result = subprocess.run(
        [
            "python",
            SCRIPT,
            "--theme-id",
            THEME_ID,
            "--theme-name",
            THEME_NAME,
            "--reviewer-reference",
            "reviewer_001",
            "--decision-reason",
            "Template evidence requires repair.",
            "--review-context-path",
            missing_context,
            "--policy-version",
            POLICY_VERSION,
            "--run-id",
            "return_cli_blocked_001",
            "--state-registry-path",
            str(STATE_PATH),
            "--evidence-log-path",
            str(EVIDENCE_PATH),
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 1
    assert "Human review return blocked" in result.stderr
    assert "does not exist" in result.stderr

    registry = ThemeStateRegistry(registry_path=STATE_PATH)
    assert registry.get_current_state(THEME_ID) == "READY_FOR_REVIEW"
