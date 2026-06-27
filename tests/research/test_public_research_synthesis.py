import json
import shutil
from pathlib import Path

import pytest

from src.hermes.public_research_synthesis import (
    PublicResearchSynthesisError,
    PublicResearchSynthesisGenerator,
)
from src.hermes.validation_evidence_log import ValidationEvidenceLog
from src.hermes.validation_evidence_summary import ValidationEvidenceSummarizer


THEME = "lead + follow up"
PLAN_PATH = (
    "reports/intelligence/validation_plans/"
    "lead_and_follow_up_validation_plan.md"
)
LOG_PATH = Path(
    "reports/intelligence/test_public_research_synthesis_log.json"
)
OUTPUT_DIR = Path(
    "reports/intelligence/test_public_research_synthesis_reports"
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


def make_generator() -> PublicResearchSynthesisGenerator:
    evidence_log = ValidationEvidenceLog(log_path=LOG_PATH)
    summarizer = ValidationEvidenceSummarizer(evidence_log)

    return PublicResearchSynthesisGenerator(
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
                        "evidence_summary": "Historical record without a source class.",
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


def test_public_research_synthesis_includes_only_gate_safe_public_evidence():
    write_legacy_entry()
    add_entry(
        evidence_type="manual_research",
        source_trust=ValidationEvidenceLog.PUBLIC_DATASET,
        source_reference="g2_support_001",
        evidence_summary="Public research supports a lead follow-up workflow need.",
        supports_validation=True,
    )
    add_entry(
        evidence_type="risk_finding",
        source_trust=ValidationEvidenceLog.PUBLIC_DATASET,
        source_reference="g2_risk_001",
        evidence_summary="Existing automation tools create setup and pricing risk.",
        supports_validation=False,
    )
    add_entry(
        evidence_type="competitor_check",
        source_trust=ValidationEvidenceLog.PUBLIC_COMPETITOR,
        source_reference="competitor_001",
        evidence_summary="An established competitor covers part of the workflow.",
        supports_validation=False,
    )

    generator = make_generator()
    synthesis = generator.build(theme=THEME)
    markdown = generator.format_markdown(synthesis)

    assert synthesis.total_entries == 4
    assert synthesis.gate_safe_public_entries == 3
    assert synthesis.public_dataset_entries == 2
    assert synthesis.public_competitor_entries == 1
    assert synthesis.public_supporting_entries == 1
    assert synthesis.public_opposing_entries == 2
    assert synthesis.entries_outside_public_synthesis == 1
    assert "g2_support_001" in markdown
    assert "g2_risk_001" in markdown
    assert "competitor_001" in markdown
    assert "legacy_owner_001" not in markdown
    assert "Public research synthesis complete; first-party pilot required." in markdown
    assert "future pilot hypothesis" in markdown.lower()


def test_public_research_synthesis_excludes_placeholder_public_evidence():
    add_entry(
        evidence_type="manual_research",
        source_trust=ValidationEvidenceLog.PUBLIC_DATASET,
        source_reference="g2_placeholder_001",
        evidence_summary="PLACEHOLDER finding from a public dataset.",
        supports_validation=True,
    )

    synthesis = make_generator().build(theme=THEME)

    assert synthesis.gate_safe_public_entries == 0
    assert synthesis.entries_outside_public_synthesis == 1
    assert synthesis.supporting_evidence == []


def test_public_research_synthesis_writes_markdown_inside_configured_output_dir():
    add_entry(
        evidence_type="manual_research",
        source_trust=ValidationEvidenceLog.PUBLIC_DATASET,
        source_reference="g2_support_001",
        evidence_summary="Public research supports a lead follow-up workflow need.",
        supports_validation=True,
    )

    generator = make_generator()
    synthesis = generator.build(theme=THEME)
    output_path = OUTPUT_DIR / "lead_and_follow_up_public_research_synthesis.md"

    written_path = generator.write_markdown(
        synthesis=synthesis,
        output_path=output_path,
    )

    assert written_path.exists()
    assert written_path.read_text(encoding="utf-8").startswith(
        "# Public Research Synthesis: lead + follow up"
    )


def test_public_research_synthesis_blocks_unsafe_output_path():
    generator = make_generator()
    synthesis = generator.build(theme=THEME)

    with pytest.raises(
        PublicResearchSynthesisError,
        match="configured output directory",
    ):
        generator.write_markdown(
            synthesis=synthesis,
            output_path="reports/intelligence/other_report.md",
        )
