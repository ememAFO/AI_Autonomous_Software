import subprocess
from pathlib import Path

from src.hermes.validation_evidence_log import ValidationEvidenceLog


SCRIPT = "scripts/generate_pilot_handoff_pack.py"
THEME = "lead + follow up"
PLAN_PATH = (
    "reports/intelligence/validation_plans/"
    "lead_and_follow_up_validation_plan.md"
)

LOG_PATH = Path(
    "reports/intelligence/test_generate_pilot_handoff_pack_cli_log.json"
)

OUTPUT_PATH = Path(
    "reports/intelligence/pilot_handoff_packs/"
    "test_cli_pilot_handoff_pack.md"
)

def cleanup_runtime_files() -> None:
    for path in [LOG_PATH, OUTPUT_PATH]:
        if path.exists():
            path.unlink()

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)


def add_public_dataset_entry() -> None:
    ValidationEvidenceLog(log_path=LOG_PATH).add_entry(
        theme=THEME,
        validation_plan_path=PLAN_PATH,
        evidence_type="manual_research",
        evidence_summary=(
            "Public research supports a lead follow-up workflow need."
        ),
        source_reference="g2_review_cli_001",
        signal_strength="medium",
        supports_validation=True,
        source_trust=ValidationEvidenceLog.PUBLIC_DATASET,
        notes="Source-classified fixture record.",
    )


def test_pilot_handoff_pack_cli_generates_future_ready_pack():
    cleanup_runtime_files()
    add_public_dataset_entry()

    result = subprocess.run(
        [
            "python",
            SCRIPT,
            "--theme",
            THEME,
            "--evidence-log-path",
            str(LOG_PATH),
            "--output-path",
            str(OUTPUT_PATH),
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    assert "Pilot Handoff Pack Generated" in result.stdout
    assert "Pilot Status: NOT_STARTED" in result.stdout
    assert "Gate-Safe Public Research Entries: 1" in result.stdout
    assert "no business has been enrolled" in result.stdout.lower()
    assert OUTPUT_PATH.exists()


def test_pilot_handoff_pack_cli_blocks_unsafe_evidence_log_path():
    cleanup_runtime_files()

    result = subprocess.run(
        [
            "python",
            SCRIPT,
            "--theme",
            THEME,
            "--evidence-log-path",
            "../../unsafe.json",
            "--output-path",
            str(OUTPUT_PATH),
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 1
    assert "Pilot handoff pack blocked" in result.stderr
    assert "reports/intelligence" in result.stderr
