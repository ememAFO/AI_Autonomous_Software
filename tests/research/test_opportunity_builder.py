import pytest

from src.analyzers.pain_extractor import PainExtractor
from src.research.models import OpportunitySource
from src.research.opportunity_builder import OpportunityBuilder


def test_opportunity_builder_creates_opportunity_from_business_pain():
    text = "I keep losing leads because I forget to follow up with clients after quotes."

    signal = PainExtractor().extract(text)
    opportunity = OpportunityBuilder().build_from_pain_signal(
        signal=signal,
        source=OpportunitySource.REDDIT,
        industry="home services",
    )

    assert opportunity.title == "Lead Follow-Up Automation"
    assert opportunity.source == OpportunitySource.REDDIT
    assert opportunity.industry == "home services"
    assert opportunity.suggested_mvp == "AI lead recovery assistant"
    assert opportunity.automation_potential >= 7
    assert text in opportunity.evidence


def test_opportunity_builder_rejects_non_business_pain():
    text = "This app is annoying but I only use it for personal notes."

    signal = PainExtractor().extract(text)

    with pytest.raises(ValueError):
        OpportunityBuilder().build_from_pain_signal(
            signal=signal,
            source=OpportunitySource.REDDIT,
            industry="general",
        )


def test_opportunity_builder_detects_booking_opportunity():
    text = "Manual appointment booking takes too long for our staff and customers miss bookings."

    signal = PainExtractor().extract(text)
    opportunity = OpportunityBuilder().build_from_pain_signal(
        signal=signal,
        source=OpportunitySource.MANUAL,
        industry="clinics",
    )

    assert opportunity.title == "Appointment Workflow Automation"
    assert opportunity.suggested_mvp == "Automated booking and reminder assistant"
