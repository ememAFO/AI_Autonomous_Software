from pathlib import Path

import pytest

from src.hermes.validation_competitor_check import (
    ValidationCompetitorCheckError,
    ValidationCompetitorCheckGenerator,
)


def test_validation_competitor_check_generates_lead_follow_up_check():
    check = ValidationCompetitorCheckGenerator().generate(
        theme="lead + follow up",
        target_user="small service business owner",
    )

    assert check.theme == "lead + follow up"
    assert check.target_user == "small service business owner"
    assert check.competitor_categories
    assert check.competitor_questions
    assert check.comparison_criteria
    assert any("crm" in item.lower() for item in check.competitor_categories)


def test_validation_competitor_check_marks_secondary_evidence_warning():
    check = ValidationCompetitorCheckGenerator().generate(
        theme="lead + follow up",
        target_user="small service business owner",
    )

    assert "secondary evidence" in check.warning.lower()
    assert any(
        "not customer proof" in item.lower()
        for item in check.evidence_logging_guidance
    )


def test_validation_competitor_check_formats_markdown():
    generator = ValidationCompetitorCheckGenerator()
    check = generator.generate(
        theme="lead + follow up",
        target_user="small service business owner",
    )

    markdown = generator.format_markdown(check)

    assert "# Validation Competitor Check: lead + follow up" in markdown
    assert "Competitor Categories" in markdown
    assert "Comparison Criteria" in markdown
    assert "Governance Note" in markdown


def test_validation_competitor_check_writes_markdown_file():
    output_path = Path(
        "reports/intelligence/test_validation_competitor_checks/"
        "lead_follow_up_competitor_check.md"
    )

    if output_path.exists():
        output_path.unlink()

    written_path = ValidationCompetitorCheckGenerator().write_markdown(
        theme="lead + follow up",
        target_user="small service business owner",
        output_path=output_path,
    )

    assert written_path.exists()

    content = written_path.read_text(encoding="utf-8")
    assert "Validation Competitor Check" in content


def test_validation_competitor_check_blocks_empty_theme():
    with pytest.raises(ValidationCompetitorCheckError):
        ValidationCompetitorCheckGenerator().generate(
            theme="",
            target_user="small service business owner",
        )


def test_validation_competitor_check_blocks_empty_target_user():
    with pytest.raises(ValidationCompetitorCheckError):
        ValidationCompetitorCheckGenerator().generate(
            theme="lead + follow up",
            target_user="",
        )


def test_validation_competitor_check_blocks_unsafe_output_path():
    with pytest.raises(ValidationCompetitorCheckError):
        ValidationCompetitorCheckGenerator().write_markdown(
            theme="lead + follow up",
            target_user="small service business owner",
            output_path="../../unsafe.md",
        )


def test_validation_competitor_check_blocks_non_markdown_output_path():
    with pytest.raises(ValidationCompetitorCheckError):
        ValidationCompetitorCheckGenerator().write_markdown(
            theme="lead + follow up",
            target_user="small service business owner",
            output_path="reports/intelligence/test_validation_competitor_checks/check.txt",
        )
