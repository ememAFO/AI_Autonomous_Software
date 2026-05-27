from src.research.pain_analysis import (
    CommercialSignal,
    PainCategory,
    PainDecision,
)
from src.research.pain_reasoner import PainReasoner


def test_pain_reasoner_accepts_lead_follow_up_pain():
    result = PainReasoner().analyze(
        "Sales teams lose leads because manual follow up after quotes takes too long.",
        industry="sales",
    )

    assert result.is_pain is True
    assert result.decision == PainDecision.ACCEPT
    assert result.pain_category == PainCategory.WORKFLOW
    assert result.commercial_signal == CommercialSignal.STRONG
    assert "manual" in result.evidence
    assert result.process_map is not None


def test_pain_reasoner_accepts_saas_pricing_and_onboarding_pain():
    result = PainReasoner().analyze(
        "The platform is expensive, hides useful features behind paywalls, "
        "and onboarding training is not that great.",
        industry="saas",
    )

    assert result.is_pain is True
    assert result.decision == PainDecision.ACCEPT
    assert result.pain_category in {
        PainCategory.ONBOARDING,
        PainCategory.ECONOMIC,
    }
    assert result.commercial_signal in {
        CommercialSignal.STRONG,
        CommercialSignal.MODERATE,
    }
    assert "paywalls" in result.evidence or "expensive" in result.evidence


def test_pain_reasoner_accepts_integration_duplicate_contact_pain():
    result = PainReasoner().analyze(
        "The integration keeps creating duplicate contacts and the issue is difficult to resolve.",
        industry="saas",
    )

    assert result.is_pain is True
    assert result.decision == PainDecision.ACCEPT
    assert result.pain_category == PainCategory.INTEGRATION
    assert any("deduplication" in cause.lower() for cause in result.possible_root_causes)


def test_pain_reasoner_rejects_cosmetic_preference():
    result = PainReasoner().analyze(
        "The dashboard colour is nice and I like the font.",
        industry="saas",
    )

    assert result.is_pain is False
    assert result.decision == PainDecision.REJECT


def test_pain_reasoner_marks_weak_pain_without_clear_consequence():
    result = PainReasoner().analyze(
        "The dashboard is confusing and the interface is difficult.",
        industry="saas",
    )

    assert result.is_pain is False
    assert result.decision in {
        PainDecision.WEAK_PAIN,
        PainDecision.REJECT,
    }


def test_pain_reasoner_distinguishes_symptom_from_possible_root_cause():
    result = PainReasoner().analyze(
        "Customer support is slow to respond and escalated issues are often unresolved.",
        industry="saas",
    )

    assert result.is_pain is True
    assert result.pain_category == PainCategory.SUPPORT
    assert result.symptom
    assert result.possible_root_causes
    assert any("escalation" in cause.lower() for cause in result.possible_root_causes)


def test_pain_reasoner_handles_empty_input():
    result = PainReasoner().analyze("", industry="sales")

    assert result.is_pain is False
    assert result.decision == PainDecision.REJECT
    assert result.confidence == 0.0
