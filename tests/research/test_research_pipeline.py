import pytest

from src.research.models import OpportunitySource
from src.research.pipeline import ResearchPipeline


def test_pipeline_creates_full_research_result():
    text = (
        "We keep losing leads because customers stop replying "
        "after quotes and manual follow up takes too long."
    )

    pipeline = ResearchPipeline()

    result = pipeline.run(
        raw_text=text,
        source=OpportunitySource.REDDIT,
        industry="roofing",
    )

    assert result.opportunity.title == "Lead Follow-Up Automation"
    assert result.score.total_score > 0
    assert result.report_path.exists()


def test_pipeline_rejects_non_business_text():
    text = "I like the colour of this application."

    pipeline = ResearchPipeline()

    with pytest.raises(ValueError):
        pipeline.run(
            raw_text=text,
            source=OpportunitySource.REDDIT,
            industry="general",
        )


def test_pipeline_generates_build_now_or_validate_recommendation():
    text = (
        "Manual appointment booking wastes time and customers "
        "miss bookings because staff forget reminders."
    )

    pipeline = ResearchPipeline()

    result = pipeline.run(
        raw_text=text,
        source=OpportunitySource.REVIEW_SITE,
        industry="clinics",
    )

    assert result.score.recommendation in {
        "BUILD_NOW",
        "VALIDATE_FIRST",
    }
