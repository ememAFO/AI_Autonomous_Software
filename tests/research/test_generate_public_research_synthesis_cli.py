import subprocess
from pathlib import Path

import pytest

from src.hermes.validation_evidence_log import ValidationEvidenceLog


SCRIPT = "scripts/generate_public_research_synthesis.py"
THEME = "lead + follow up"
PLAN_PATH = (
    "reports/intelligence/validation_plans/"
    "lead_and_follow_up_validation_plan.md"
)
LOG_PATH = Path(
    "reports/intelligence/test_generate_public_research_synthesis_cli_log.json"
)
OUTPUT_DIR = Path("reports/intelligence/public_research_synthesis")
OUTPUT_PATH = OUTPUT_DIR / "test_lead_and_follow_up_public_research_synthesis.md"


def cleanup_runtime_files() -> None:
    if LOG_PATH.exists():
        LOG_PATH.unlink()

    if OUTPUT_PATH.exists():
        OUTPUT_PATH.unlink()


@pytest.fixture(autouse=True)
def clean_runtime_files():
    cleanup_runtime_files()
    yield
    cleanup_runtime_files()


def add_public_dataset_entry() -> None:
    ValidationEvidenceLog(log_path=LOG_PATH).add_entry(
        theme=THEME,
        validation_plan_path=PLAN_PATH,
        evidence_type="manual_research",
        evidence_summary=(
            "Public dataset evidence shows a small business automating "
            "inbound leads into a follow-up workflow."
        ),
        source_reference="g2_cli_001",
        signal_strength="medium",
        supports_validation=True,
        source_trust=ValidationEvidenceLog.PUBLIC_DATASET,
        notes="Public research evidence only.",
    )


def run_cli(*, output_path: str | None = None) -> subprocess.CompletedProcess[str]:
    command = [
        "python",
        SCRIPT,
        "--theme",
        THEME,
        "--evidence-log-path",
        str(LOG_PATH),
    ]

    if output_path is not None:
        command.extend(["--output-path", output_path])

    return subprocess.run(
        command,
        capture_output=True,
        text=True,
        check=False,
    )


def test_public_research_synthesis_cli_writes_read_only_report():
    add_public_dataset_entry()

    result = run_cli(output_path=str(OUTPUT_PATH))

    assert result.returncode == 0
    assert "Public Research Synthesis Generated" in result.stdout
    assert "Gate-Safe Public Research Entries: 1" in result.stdout
    assert "Public Dataset Entries: 1" in result.stdout
    assert "Decision Boundary: Public research synthesis complete" in result.stdout
    assert OUTPUT_PATH.exists()

    content = OUTPUT_PATH.read_text(encoding="utf-8")
    assert "g2_cli_001" in content
    assert "Public research synthesis complete; first-party pilot required." in content


def test_public_research_synthesis_cli_blocks_output_outside_default_directory():
    add_public_dataset_entry()

    result = run_cli(
        output_path="reports/intelligence/public_research_outside_scope.md"
    )

    assert result.returncode == 1
    assert "Public research synthesis blocked" in result.stderr
    assert "configured output directory" in result.stderr
