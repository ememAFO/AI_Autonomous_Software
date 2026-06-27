import json
import subprocess
from pathlib import Path

from src.hermes.validation_evidence_log import ValidationEvidenceLog


SCRIPT = "scripts/generate_validation_evidence_verification_report.py"

THEME = "lead + follow up"

EVIDENCE_LOG_PATH = Path(
    "reports/intelligence/"
    "test_generate_validation_evidence_verification_cli_log.json"
)

OUTPUT_PATH = Path(
    "reports/intelligence/"
    "test_validation_evidence_verification_reports/"
    "cli_verification_report.md"
)


def clean_runtime_files() -> None:
    for path in [EVIDENCE_LOG_PATH, OUTPUT_PATH]:
        if path.exists():
            path.unlink()

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)


def write_legacy_entry() -> None:
    payload = {
        "evidence": [
            {
                "theme": THEME,
                "validation_plan_path": (
                    "reports/intelligence/validation_plans/"
                    "lead_and_follow_up_validation_plan.md"
                ),
                "evidence_type": "customer_interview",
                "evidence_summary": (
                    "Historical validation record without a declared "
                    "source-trust class."
                ),
                "source_reference": "legacy_owner_001",
                "signal_strength": "medium",
                "supports_validation": True,
                "timestamp": "2026-06-20T00:00:00+00:00",
                "notes": "Historical record.",
            }
        ]
    }

    EVIDENCE_LOG_PATH.write_text(
        json.dumps(payload, indent=2),
        encoding="utf-8",
    )


def add_public_dataset_entry() -> None:
    log = ValidationEvidenceLog(log_path=EVIDENCE_LOG_PATH)

    log.add_entry(
        theme=THEME,
        validation_plan_path=(
            "reports/intelligence/validation_plans/"
            "lead_and_follow_up_validation_plan.md"
        ),
        evidence_type="manual_research",
        evidence_summary=(
            "Public dataset review shows a small business automating "
            "form leads into a CRM and follow-up email."
        ),
        source_reference="g2_review_test_001",
        signal_strength="medium",
        supports_validation=True,
        source_trust=ValidationEvidenceLog.PUBLIC_DATASET,
        notes="Public research evidence only.",
    )


def run_cli() -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            "python",
            SCRIPT,
            "--theme",
            THEME,
            "--evidence-log-path",
            str(EVIDENCE_LOG_PATH),
            "--output-path",
            str(OUTPUT_PATH),
        ],
        capture_output=True,
        text=True,
        check=False,
    )


def test_verification_cli_labels_legacy_entries_as_gate_excluded():
    clean_runtime_files()
    write_legacy_entry()

    result = run_cli()

    assert result.returncode == 0
    assert "Gate-Safe Evidence Entries: 0" in result.stdout
    assert "Gate-Excluded Evidence Entries: 1" in result.stdout
    assert "Legacy Unverified Entries: 1" in result.stdout
    assert "Suspect / Placeholder Entries: 0" in result.stdout
    assert "Gate-Excluded Evidence Entries:" in result.stdout
    assert "trust=legacy_unverified" in result.stdout
    assert "exclusion_reasons=legacy_unverified" in result.stdout
    assert "markers=None" in result.stdout
    assert "Suspect Entries:" not in result.stdout


def test_verification_cli_keeps_public_dataset_evidence_gate_safe():
    clean_runtime_files()
    add_public_dataset_entry()

    result = run_cli()

    assert result.returncode == 0
    assert "Gate-Safe Evidence Entries: 1" in result.stdout
    assert "Gate-Excluded Evidence Entries: 0" in result.stdout
    assert "Legacy Unverified Entries: 0" in result.stdout
    assert "Suspect / Placeholder Entries: 0" in result.stdout
    assert "No gate-excluded entries detected." in result.stdout
