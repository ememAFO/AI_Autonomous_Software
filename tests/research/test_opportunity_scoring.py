from src.research.models import Opportunity, OpportunitySource
from src.research.scoring import OpportunityScoringEngine


def test_scoring_engine_recommends_build_now_for_strong_opportunity():
    opportunity = Opportunity(
        title="Lead follow-up automation",
        pain_point="Service businesses lose revenue because they forget to follow up leads.",
        source=OpportunitySource.REDDIT,
        industry="home services",
        frequency=9,
        urgency=9,
        monetization=9,
        retention_impact=8,
        competition_gap=8,
        automation_potential=9,
        implementation_difficulty=2,
        evidence=["Repeated complaints about manual lead follow-up."],
        suggested_mvp="AI lead recovery assistant",
    )

    result = OpportunityScoringEngine().score(opportunity)

    assert result.total_score >= 8
    assert result.recommendation == "BUILD_NOW"


def test_scoring_engine_rejects_weak_opportunity():
    opportunity = Opportunity(
        title="Nice-to-have dashboard theme",
        pain_point="Some users want a different dashboard colour.",
        source=OpportunitySource.MANUAL,
        industry="general SaaS",
        frequency=2,
        urgency=2,
        monetization=1,
        retention_impact=1,
        competition_gap=2,
        automation_potential=1,
        implementation_difficulty=6,
        evidence=["One minor complaint."],
        suggested_mvp="Theme selector",
    )

    result = OpportunityScoringEngine().score(opportunity)

    assert result.total_score < 5
    assert result.recommendation == "REJECT"


def test_scoring_engine_flags_hard_builds_in_reasons():
    opportunity = Opportunity(
        title="Full finance automation platform",
        pain_point="Businesses want full finance automation.",
        source=OpportunitySource.MANUAL,
        industry="finance",
        frequency=8,
        urgency=8,
        monetization=9,
        retention_impact=8,
        competition_gap=5,
        automation_potential=7,
        implementation_difficulty=9,
        evidence=["Complex finance workflows."],
        suggested_mvp="Finance automation suite",
    )

    result = OpportunityScoringEngine().score(opportunity)

    assert "Implementation difficulty is high, so MVP scope should be reduced." in result.reasons
