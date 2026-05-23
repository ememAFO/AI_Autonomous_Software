from src.analyzers.pain_extractor import PainSignal
from src.research.models import Opportunity, OpportunitySource


class OpportunityBuilder:
    """
    Converts detected pain signals into structured opportunities.

    This is intentionally simple for v1.
    Later, Hermes can improve the title, industry classification,
    MVP suggestion, and scoring quality.
    """

    def build_from_pain_signal(
        self,
        signal: PainSignal,
        source: OpportunitySource,
        industry: str,
        title: str | None = None,
    ) -> Opportunity:
        if not signal.is_business_pain:
            raise ValueError("Cannot build opportunity from non-business pain signal")

        opportunity_title = title or self._generate_title(signal.text)
        suggested_mvp = self._suggest_mvp(signal.text)

        return Opportunity(
            title=opportunity_title,
            pain_point=signal.text,
            source=source,
            industry=industry,
            frequency=self._estimate_frequency(signal),
            urgency=self._estimate_urgency(signal),
            monetization=self._estimate_monetization(signal),
            retention_impact=self._estimate_retention_impact(signal),
            competition_gap=self._estimate_competition_gap(signal),
            automation_potential=self._estimate_automation_potential(signal),
            implementation_difficulty=self._estimate_implementation_difficulty(signal),
            evidence=[signal.text],
            suggested_mvp=suggested_mvp,
        )

    def _generate_title(self, text: str) -> str:
        lowered = text.lower()

        if "lead" in lowered or "quote" in lowered:
            return "Lead Follow-Up Automation"
        if "booking" in lowered or "appointment" in lowered:
            return "Appointment Workflow Automation"
        if "invoice" in lowered:
            return "Invoice Workflow Automation"

        return "Business Workflow Automation Opportunity"

    def _suggest_mvp(self, text: str) -> str:
        lowered = text.lower()

        if "lead" in lowered or "quote" in lowered or "follow up" in lowered:
            return "AI lead recovery assistant"
        if "booking" in lowered or "appointment" in lowered:
            return "Automated booking and reminder assistant"
        if "invoice" in lowered:
            return "Invoice follow-up and reminder assistant"

        return "Small workflow automation assistant"

    def _estimate_frequency(self, signal: PainSignal) -> float:
        return min(10.0, 5.0 + len(signal.matched_terms) * 0.4)

    def _estimate_urgency(self, signal: PainSignal) -> float:
        return min(10.0, signal.frustration_score + 1.0)

    def _estimate_monetization(self, signal: PainSignal) -> float:
        text = signal.text.lower()

        if any(term in text for term in ["revenue", "sales", "leads", "quotes", "invoice"]):
            return 8.0

        return 6.0

    def _estimate_retention_impact(self, signal: PainSignal) -> float:
        text = signal.text.lower()

        if any(term in text for term in ["customer", "client", "support", "booking"]):
            return 7.0

        return 5.0

    def _estimate_competition_gap(self, signal: PainSignal) -> float:
        return 6.0

    def _estimate_automation_potential(self, signal: PainSignal) -> float:
        text = signal.text.lower()

        if any(term in text for term in ["manual", "follow up", "booking", "reminder", "repetitive"]):
            return 9.0

        return 6.5

    def _estimate_implementation_difficulty(self, signal: PainSignal) -> float:
        text = signal.text.lower()

        if any(term in text for term in ["billing", "payment", "finance", "bank"]):
            return 8.0

        return 4.0
