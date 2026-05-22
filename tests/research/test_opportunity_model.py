import pytest

from src.research.models import Opportunity, OpportunitySource


def test_opportunity_can_be_created():
    opportunity = Opportunity(
        title="Missed quote follow-up",
        pain_point="Small businesses lose leads because customers stop replying after quotes.",
        source=OpportunitySource.REDDIT,
        industry="roofing",
        frequency=8,
        urgency=8,
        monetization=9,
        retention_impact=7,
        competition_gap=6,
        automation_potential=9,
        implementation_difficulty=4,
        evidence=["Several users complained about manual follow-up."],
        suggested_mvp="AI lead recovery assistant",
    )

    assert opportunity.title == "Missed quote follow-up"
    assert opportunity.source == OpportunitySource.REDDIT


def test_opportunity_rejects_empty_title():
    with pytest.raises(ValueError):
        Opportunity(
            title="",
            pain_point="Valid pain point",
            source=OpportunitySource.REDDIT,
            industry="roofing",
            frequency=5,
            urgency=5,
            monetization=5,
            retention_impact=5,
            competition_gap=5,
            automation_potential=5,
            implementation_difficulty=5,
        )


def test_opportunity_rejects_score_outside_zero_to_ten():
    with pytest.raises(ValueError):
        Opportunity(
            title="Bad score",
            pain_point="Valid pain point",
            source=OpportunitySource.REDDIT,
            industry="roofing",
            frequency=11,
            urgency=5,
            monetization=5,
            retention_impact=5,
            competition_gap=5,
            automation_potential=5,
            implementation_difficulty=5,
        )
