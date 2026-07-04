import json
import shutil
from pathlib import Path

import pytest

from src.hermes.pilot_handoff_pack import (
    PilotHandoffPackError,
    PilotHandoffPackGenerator,
)
from src.hermes.validation_evidence_log import ValidationEvidenceLog
from src.hermes.validation_evidence_summary import ValidationEvidenceSummarizer


THEME = "lead + follow up"
PLAN_PATH = (
    "reports/intelligence/validation_plans/"
    "lead_and_follow_up_validation_plan.md"
)
LOG_PATH = Path(
    "reports/intelligence/test_pilot_handoff_pack_log.json"
)
OUTPUT_DIR = Path(
    "reports/intelligence/test_pilot_handoff_packs"
)


def cleanup_runtime_files() -> None:
    if LOG_PATH.exists():
        LOG_PATH.unlink()

    if OUTPUT_DIR.exists():
        shutil.rmtree(OUTPUT_DIR)


@pytest.fixture(autouse=True)
def clean_runtime_files():
    cleanup_runtime_files()
    yield
    cleanup_runtime_files()


def make_generator() -> PilotHandoffPackGenerator:
    evidence_log = ValidationEvidenceLog(log_path=LOG_PATH)
    summarizer = ValidationEvidenceSummarizer(evidence_log)

    return PilotHandoffPackGenerator(
        evidence_summarizer=summarizer,
        output_dir=OUTPUT_DIR,
    )


def write_legacy_entry() -> None:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    LOG_PATH.write_text(
        json.dumps(
            {
                "evidence": [
                    {
                        "theme": THEME,
                        "validation_plan_path": PLAN_PATH,
                        "evidence_type": "customer_interview",
                        "evidence_summary": (
                            "Historical record without a source class."
                        ),
                        "source_reference": "legacy_owner_001",
                        "signal_strength": "medium",
                        "supports_validation": True,
                        "timestamp": "2026-06-24T00:00:00+00:00",
                        "notes": "Historical audit record.",
                    }
                ]
            },
            indent=2,
        ),
        encoding="utf-8",
    )


def add_entry(
    *,
    evidence_type: str,
    source_trust: str,
    source_reference: str,
    evidence_summary: str,
    supports_validation: bool,
) -> None:
    ValidationEvidenceLog(log_path=LOG_PATH).add_entry(
        theme=THEME,
        validation_plan_path=PLAN_PATH,
        evidence_type=evidence_type,
        evidence_summary=evidence_summary,
        source_reference=source_reference,
        signal_strength="medium",
        supports_validation=supports_validation,
        source_trust=source_trust,
        notes="Source-classified fixture record.",
    )


def test_pilot_handoff_pack_is_future_ready_without_claiming_a_pilot_started():
    write_legacy_entry()
    add_entry(
        evidence_type="manual_research",
        source_trust=ValidationEvidenceLog.PUBLIC_DATASET,
        source_reference="g2_support_001",
        evidence_summary=(
            "Public research supports a lead follow-up workflow need."
        ),
        supports_validation=True,
    )
    add_entry(
        evidence_type="risk_finding",
        source_trust=ValidationEvidenceLog.PUBLIC_DATASET,
        source_reference="g2_risk_001",
        evidence_summary=(
            "Existing automation tools create setup and pricing risk."
        ),
        supports_validation=False,
    )
    add_entry(
        evidence_type="customer_interview",
        source_trust=ValidationEvidenceLog.HUMAN_ATTESTED_FIRST_PARTY,
        source_reference="owner_001",
        evidence_summary=(
            "A real owner described a delayed enquiry follow-up problem."
        ),
        supports_validation=True,
    )

    generator = make_generator()
    entry_count_before = len(
        generator.evidence_summarizer.evidence_log.list_entries_for_theme(
            THEME
        )
    )

    pack = generator.build(theme=THEME)
    markdown = generator.format_markdown(pack)

    assert pack.pilot_status == "NOT_STARTED"
    assert pack.gate_safe_public_research_entries == 2
    assert pack.public_supporting_entries == 1
    assert pack.public_challenging_entries == 1
    assert pack.gate_safe_first_party_primary_entries == 1
    assert pack.entries_outside_public_research == 2
    assert "Pilot Status: NOT_STARTED" in markdown
    assert "No business has been enrolled" in markdown
    assert "Do not place names, email addresses, phone numbers" in markdown
    assert "add_primary_evidence.py only after a real event" in markdown
    assert "does not collect data" in markdown

    entry_count_after = len(
        generator.evidence_summarizer.evidence_log.list_entries_for_theme(
            THEME
        )
    )
    assert entry_count_after == entry_count_before


def test_pilot_handoff_pack_writes_markdown_inside_configured_output_dir():
    add_entry(
        evidence_type="manual_research",
        source_trust=ValidationEvidenceLog.PUBLIC_DATASET,
        source_reference="g2_support_001",
        evidence_summary=(
            "Public research supports a lead follow-up workflow need."
        ),
        supports_validation=True,
    )

    generator = make_generator()
    pack = generator.build(theme=THEME)
    output_path = OUTPUT_DIR / "lead_and_follow_up_pilot_handoff_pack.md"

    written_path = generator.write_markdown(
        pack=pack,
        output_path=output_path,
    )

    assert written_path.exists()
    content = written_path.read_text(encoding="utf-8")
    assert content.startswith("# Pilot Handoff Pack: lead + follow up")
    assert "Future Pilot Hypothesis" in content


def test_pilot_handoff_pack_blocks_unsafe_output_path():
    generator = make_generator()
    pack = generator.build(theme=THEME)

    with pytest.raises(
        PilotHandoffPackError,
        match="configured output directory",
    ):
        generator.write_markdown(
            pack=pack,
            output_path="reports/intelligence/other_pilot_pack.md",
        )


def test_pilot_handoff_pack_blocks_ambiguous_evidence_dependencies():
    evidence_log = ValidationEvidenceLog(log_path=LOG_PATH)
    summarizer = ValidationEvidenceSummarizer(evidence_log)

    with pytest.raises(
        PilotHandoffPackError,
        match="either evidence_log or evidence_summarizer",
    ):
        PilotHandoffPackGenerator(
            evidence_log=evidence_log,
            evidence_summarizer=summarizer,
            output_dir=OUTPUT_DIR,
        )
