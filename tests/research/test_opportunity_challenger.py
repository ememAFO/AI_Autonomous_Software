from src.research.models import Opportunity, OpportunitySource
from src.research.opportunity_challenger import (
    ChallengeRecommendation,
    OpportunityChallenger,
    ProblemType,
)


def make_opportunity(
    *,
    title: str = "Lead follow-up automation",
    pain_point: str = "Small businesses lose leads because clients stop replying after quotes and manual follow up takes too long.",
    source: OpportunitySource = OpportunitySource.REDDIT,
    industry: str = "home services",
    frequency: float = 8,
    urgency: float = 8,
    monetization: float = 8,
    retention_impact: float = 7,
    competition_gap: float = 6,
    automation_potential: float = 9,
    implementation_difficulty: float = 4,
    evidence: list[str] | None = None,
    suggested_mvp: str | None = "AI lead recovery assistant",
) -> Opportunity:
    return Opportunity(
        title=title,
        pain_point=pain_point,
        source=source,
        industry=industry,
        frequency=frequency,
        urgency=urgency,
        monetization=monetization,
        retention_impact=retention_impact,
        competition_gap=competition_gap,
        automation_potential=automation_potential,
        implementation_difficulty=implementation_difficulty,
        evidence=evidence or [pain_point],
        suggested_mvp=suggested_mvp,
    )


def test_opportunity_challenger_allows_strong_workflow_opportunity():
    opportunity = make_opportunity()

    result = OpportunityChallenger().challenge(opportunity)

    assert result.should_continue is True
    assert result.problem_type == ProblemType.WORKFLOW_FAILURE
    assert result.recommendation == ChallengeRecommendation.CONTINUE_TO_SCORING
    assert "Revenue leakage" in result.reframed_problem
    assert result.validation_questions


def test_opportunity_challenger_rejects_cosmetic_false_opportunity():
    opportunity = make_opportunity(
        title="Dashboard colour picker",
        pain_point="Some users want a nicer dashboard colour theme.",
        industry="saas",
        frequency=2,
        urgency=2,
        monetization=1,
        retention_impact=1,
        competition_gap=2,
        automation_potential=1,
        implementation_difficulty=2,
        suggested_mvp="Theme selector",
    )

    result = OpportunityChallenger().challenge(opportunity)

    assert result.should_continue is False
    assert result.recommendation == ChallengeRecommendation.REJECT_FALSE_OPPORTUNITY
    assert result.false_opportunity_risks


def test_opportunity_challenger_reframes_booking_problem():
    opportunity = make_opportunity(
        title="Appointment booking issue",
        pain_point="Manual appointment booking causes missed bookings and customers forget reminders.",
        industry="clinics",
        frequency=8,
        urgency=8,
        monetization=7,
        retention_impact=8,
        automation_potential=8,
        suggested_mvp="Booking reminder assistant",
    )

    result = OpportunityChallenger().challenge(opportunity)

    assert result.should_continue is True
    assert "missed bookings" in result.reframed_problem
    assert result.problem_type == ProblemType.WORKFLOW_FAILURE


def test_opportunity_challenger_flags_high_difficulty_opportunity_for_reframing():
    opportunity = make_opportunity(
        title="Full finance automation platform",
        pain_point="Businesses want finance automation for payments, invoices, reporting, compliance, and reconciliation.",
        industry="accounting",
        frequency=8,
        urgency=8,
        monetization=7,
        retention_impact=8,
        automation_potential=7,
        implementation_difficulty=9,
        suggested_mvp="Full finance automation suite",
    )

    result = OpportunityChallenger().challenge(opportunity)

    assert result.should_continue is True
    assert result.recommendation == ChallengeRecommendation.REFRAME_OPPORTUNITY
    assert any("overengineering" in item for item in result.hidden_assumptions)


def test_opportunity_challenger_validates_unclear_opportunity_before_scoring():
    opportunity = make_opportunity(
        title="General business dashboard",
        pain_point="Business owners want a better dashboard.",
        industry="saas",
        frequency=5,
        urgency=5,
        monetization=5,
        retention_impact=5,
        automation_potential=5,
        implementation_difficulty=5,
        suggested_mvp="Dashboard builder",
    )

    result = OpportunityChallenger().challenge(opportunity)

    assert result.should_continue is True
    assert result.recommendation == ChallengeRecommendation.VALIDATE_BEFORE_SCORING


def test_opportunity_challenger_detects_training_issue():
    opportunity = make_opportunity(
        title="CRM onboarding problem",
        pain_point="Sales staff do not know how to use the CRM because onboarding is poor.",
        industry="sales",
        frequency=6,
        urgency=5,
        monetization=5,
        retention_impact=5,
        automation_potential=3,
        implementation_difficulty=4,
        suggested_mvp="CRM training assistant",
    )

    result = OpportunityChallenger().challenge(opportunity)

    assert result.problem_type == ProblemType.TRAINING_ISSUE
    assert result.recommendation in {
        ChallengeRecommendation.VALIDATE_BEFORE_SCORING,
        ChallengeRecommendation.REJECT_FALSE_OPPORTUNITY,
    }


def test_opportunity_challenger_adds_crm_assumption():
    opportunity = make_opportunity(
        title="CRM admin issue",
        pain_point="Sales teams waste time with CRM data entry and manual sales reporting.",
        industry="sales",
        suggested_mvp="CRM note summarizer",
    )

    result = OpportunityChallenger().challenge(opportunity)

    assert any("CRM workflow friction" in item for item in result.hidden_assumptions)


def test_opportunity_challenger_rejects_low_automation_low_monetization():
    opportunity = make_opportunity(
        title="Personal preference tracker",
        pain_point="Users sometimes forget personal preferences in notes.",
        industry="saas",
        frequency=2,
        urgency=2,
        monetization=2,
        retention_impact=1,
        competition_gap=2,
        automation_potential=2,
        implementation_difficulty=5,
        suggested_mvp="Preference tracker",
    )

    result = OpportunityChallenger().challenge(opportunity)

    assert result.should_continue is False
    assert result.recommendation == ChallengeRecommendation.REJECT_FALSE_OPPORTUNITY
