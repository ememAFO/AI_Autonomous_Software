from src.research.models import Opportunity, OpportunitySource
from src.research.report_generator import OpportunityReportGenerator
from src.research.scoring import OpportunityScoringEngine
import pytest


def test_opportunity_report_generator_creates_markdown_file(tmp_path):
    opportunity = Opportunity(
        title="Lead Recovery Assistant",
        pain_point="Small businesses lose leads because they forget to follow up.",
        source=OpportunitySource.REDDIT,
        industry="home services",
        frequency=9,
        urgency=8,
        monetization=9,
        retention_impact=8,
        competition_gap=7,
        automation_potential=9,
        implementation_difficulty=3,
        evidence=["Repeated complaints about missed follow-ups."],
        suggested_mvp="AI lead recovery assistant",
    )

    score = OpportunityScoringEngine().score(opportunity)
    generator = OpportunityReportGenerator(output_dir="reports/opportunities")

    report_path = generator.generate(score)

    assert report_path.exists()

    content = report_path.read_text(encoding="utf-8")

    assert "# Opportunity Report: Lead Recovery Assistant" in content
    assert "AI lead recovery assistant" in content
    assert "Repeated complaints about missed follow-ups." in content
    assert score.recommendation in content



def test_report_generator_blocks_path_traversal_output_dir():
    with pytest.raises(ValueError):
        OpportunityReportGenerator(output_dir="../../unsafe")


def test_report_generator_keeps_reports_inside_reports_folder():
    generator = OpportunityReportGenerator(output_dir="reports/opportunities")

    safe_path = generator._safe_report_path("safe_report")

    assert "reports/opportunities" in str(safe_path)
    assert safe_path.name == "safe_report.md"
