from pathlib import Path

import pytest

from src.hermes.validation_interview_template import (
    ValidationInterviewTemplateError,
    ValidationInterviewTemplateGenerator,
)


def test_validation_interview_template_generates_lead_follow_up_questions():
    template = ValidationInterviewTemplateGenerator().generate(
        theme="lead + follow up",
        target_user="small service business owner",
    )

    assert template.theme == "lead + follow up"
    assert template.target_user == "small service business owner"
    assert template.discovery_questions
    assert template.willingness_to_pay_questions
    assert template.risk_questions
    assert any("follow" in question.lower() for question in template.discovery_questions)


def test_validation_interview_template_includes_counter_evidence_guidance():
    template = ValidationInterviewTemplateGenerator().generate(
        theme="lead + follow up",
        target_user="small service business owner",
    )

    assert any("weakens" in item.lower() for item in template.evidence_logging_guidance)
    assert "Avoid leading" in template.warning


def test_validation_interview_template_formats_markdown():
    generator = ValidationInterviewTemplateGenerator()

    template = generator.generate(
        theme="lead + follow up",
        target_user="small service business owner",
    )

    markdown = generator.format_markdown(template)

    assert "# Validation Interview Template: lead + follow up" in markdown
    assert "Screening Questions" in markdown
    assert "Willingness-To-Pay Questions" in markdown
    assert "Risk / Counter-Evidence Questions" in markdown
    assert "Governance Note" in markdown


def test_validation_interview_template_writes_markdown_file():
    output_path = Path(
        "reports/intelligence/test_validation_interviews/"
        "lead_follow_up_interview_template.md"
    )

    if output_path.exists():
        output_path.unlink()

    written_path = ValidationInterviewTemplateGenerator().write_markdown(
        theme="lead + follow up",
        target_user="small service business owner",
        output_path=output_path,
    )

    assert written_path.exists()

    content = written_path.read_text(encoding="utf-8")
    assert "Validation Interview Template" in content


def test_validation_interview_template_blocks_empty_theme():
    with pytest.raises(ValidationInterviewTemplateError):
        ValidationInterviewTemplateGenerator().generate(
            theme="",
            target_user="small service business owner",
        )


def test_validation_interview_template_blocks_empty_target_user():
    with pytest.raises(ValidationInterviewTemplateError):
        ValidationInterviewTemplateGenerator().generate(
            theme="lead + follow up",
            target_user="",
        )


def test_validation_interview_template_blocks_unsafe_output_path():
    with pytest.raises(ValidationInterviewTemplateError):
        ValidationInterviewTemplateGenerator().write_markdown(
            theme="lead + follow up",
            target_user="small service business owner",
            output_path="../../unsafe.md",
        )


def test_validation_interview_template_blocks_non_markdown_output_path():
    with pytest.raises(ValidationInterviewTemplateError):
        ValidationInterviewTemplateGenerator().write_markdown(
            theme="lead + follow up",
            target_user="small service business owner",
            output_path="reports/intelligence/test_validation_interviews/template.txt",
        )
