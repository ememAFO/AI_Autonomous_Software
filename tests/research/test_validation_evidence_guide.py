from pathlib import Path

import pytest

from src.hermes.validation_evidence_guide import (
    ValidationEvidenceGuideGenerator,
)
from src.hermes.validation_evidence_log import ValidationEvidenceLog
from src.hermes.validation_evidence_summary import ValidationEvidenceSummarizer


def clean_path(path: str) -> None:
    file_path = Path(path)

    if file_path.exists():
        file_path.unlink()


def make_log(
    path: str = "reports/intelligence/test_validation_evidence_guide_log.json",
) -> ValidationEvidenceLog:
    clean_path(path)
    return ValidationEvidenceLog(log_path=path)


def make_generator(log: ValidationEvidenceLog) -> ValidationEvidenceGuideGenerator:
    return ValidationEvidenceGuideGenerator(
        ValidationEvidenceSummarizer(log)
    )


def test_validation_evidence_guide_marks_missing_entries_for_early_signal():
    log = make_log()
    log.add_entry(
        theme="lead + follow up",
        validation_plan_path=(
            "reports/intelligence/validation_plans/"
            "lead_and_follow_up_validation_plan.md"
        ),
        evidence_type="customer_interview",
        evidence_summary="User confirmed delayed follow-up causes lost leads.",
        source_reference="Interview 1",
        signal_strength="strong",
        supports_validation=True,
        source_trust=ValidationEvidenceLog.HUMAN_ATTESTED_FIRST_PARTY,
    )

    guide = make_generator(log).generate("lead + follow up")

    assert guide.evidence_status == "EARLY_SUPPORTING_SIGNAL"
    assert guide.total_entries == 1
    assert guide.additional_entries_needed == 4
    assert "human_attested_first_party:customer_interview" in guide.recommended_evidence_types
    assert "human_attested_first_party:willingness_to_pay" in guide.recommended_evidence_types


def test_validation_evidence_guide_handles_no_evidence():
    log = make_log("reports/intelligence/test_validation_evidence_guide_empty.json")

    guide = make_generator(log).generate("lead + follow up")

    assert guide.evidence_status == "NO_EVIDENCE"
    assert guide.total_entries == 0
    assert guide.additional_entries_needed == 5
    assert "No validation evidence" in guide.warning


def test_validation_evidence_guide_formats_markdown():
    log = make_log("reports/intelligence/test_validation_evidence_guide_markdown.json")
    generator = make_generator(log)

    guide = generator.generate("lead + follow up")
    markdown = generator.format_markdown(guide)

    assert "# Validation Evidence Collection Guide: lead + follow up" in markdown
    assert "Current Evidence Status" in markdown
    assert "Recommended Evidence Types" in markdown
    assert "Governance Note" in markdown


def test_validation_evidence_guide_writes_markdown_file():
    log = make_log("reports/intelligence/test_validation_evidence_guide_write_log.json")
    generator = make_generator(log)

    output_path = Path(
        "reports/intelligence/test_validation_guides/"
        "lead_follow_up_evidence_guide.md"
    )

    if output_path.exists():
        output_path.unlink()

    written_path = generator.write_markdown(
        theme="lead + follow up",
        output_path=output_path,
    )

    assert written_path.exists()

    content = written_path.read_text(encoding="utf-8")
    assert "Validation Evidence Collection Guide" in content


def test_validation_evidence_guide_blocks_unsafe_output_path():
    log = make_log("reports/intelligence/test_validation_evidence_guide_unsafe.json")
    generator = make_generator(log)

    with pytest.raises(ValueError):
        generator.write_markdown(
            theme="lead + follow up",
            output_path="../../unsafe.md",
        )


def test_validation_evidence_guide_blocks_non_markdown_output_path():
    log = make_log("reports/intelligence/test_validation_evidence_guide_non_md.json")
    generator = make_generator(log)

    with pytest.raises(ValueError):
        generator.write_markdown(
            theme="lead + follow up",
            output_path="reports/intelligence/test_validation_guides/guide.txt",
        )

def test_validation_evidence_guide_shows_primary_secondary_and_risk_counts():
    log = make_log(
        "reports/intelligence/test_validation_evidence_guide_evidence_mix.json"
    )

    log.add_entry(
        theme="lead + follow up",
        validation_plan_path=(
            "reports/intelligence/validation_plans/"
            "lead_and_follow_up_validation_plan.md"
        ),
        evidence_type="customer_interview",
        evidence_summary="User confirmed delayed follow-up causes lost leads.",
        source_reference="Interview 1",
        signal_strength="strong",
        supports_validation=True,
        source_trust=ValidationEvidenceLog.HUMAN_ATTESTED_FIRST_PARTY,
    )

    log.add_entry(
        theme="lead + follow up",
        validation_plan_path=(
            "reports/intelligence/validation_plans/"
            "lead_and_follow_up_validation_plan.md"
        ),
        evidence_type="competitor_check",
        evidence_summary="Existing CRM tools may be too broad for small businesses.",
        source_reference="manual_competitor_check_001",
        signal_strength="medium",
        supports_validation=True,
        source_trust=ValidationEvidenceLog.PUBLIC_COMPETITOR,
    )

    guide = make_generator(log).generate("lead + follow up")
    markdown = make_generator(log).format_markdown(guide)

    assert guide.primary_entries == 1
    assert guide.secondary_entries == 1
    assert guide.risk_entries == 0
    assert guide.primary_entries_needed == 1
    assert "Raw Primary-Type Entries: 1" in markdown
    assert "Secondary Entries: 1" in markdown
    assert "Risk Entries: 0" in markdown
    assert "First-Party Primary Entries Needed Before Human Review: 1" in markdown
    assert "not enough for human review" in guide.warning
