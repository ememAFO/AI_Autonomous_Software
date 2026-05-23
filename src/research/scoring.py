from dataclasses import dataclass

from src.research.models import Opportunity


@dataclass(frozen=True)
class OpportunityScore:
    opportunity: Opportunity
    total_score: float
    recommendation: str
    reasons: list[str]


class OpportunityScoringEngine:
    """
    Scores opportunities from 0 to 10.

    Higher score means stronger business opportunity.

    implementation_difficulty is subtracted because harder builds are less attractive
    for an early MVP.
    """

    def score(self, opportunity: Opportunity) -> OpportunityScore:
        total = (
            opportunity.frequency * 0.25
            + opportunity.urgency * 0.20
            + opportunity.monetization * 0.20
            + opportunity.retention_impact * 0.10
            + opportunity.competition_gap * 0.10
            + opportunity.automation_potential * 0.10
            - opportunity.implementation_difficulty * 0.05
        )

        total = round(max(0, min(10, total)), 2)

        recommendation = self._recommend(total)
        reasons = self._reasons(opportunity, total)

        return OpportunityScore(
            opportunity=opportunity,
            total_score=total,
            recommendation=recommendation,
            reasons=reasons,
        )

    def _recommend(self, total_score: float) -> str:
        if total_score >= 8:
            return "BUILD_NOW"
        if total_score >= 6:
            return "VALIDATE_FIRST"
        if total_score >= 5:
            return "WATCH"
        return "REJECT"

    def _reasons(self, opportunity: Opportunity, total_score: float) -> list[str]:
        reasons: list[str] = []

        if opportunity.frequency >= 7:
            reasons.append("The pain appears frequently.")
        if opportunity.urgency >= 7:
            reasons.append("The problem feels urgent to users.")
        if opportunity.monetization >= 7:
            reasons.append("The opportunity has strong monetization potential.")
        if opportunity.automation_potential >= 7:
            reasons.append("The workflow is suitable for automation.")
        if opportunity.implementation_difficulty >= 7:
            reasons.append("Implementation difficulty is high, so MVP scope should be reduced.")
        if total_score < 5:
            reasons.append("The opportunity is currently too weak to prioritize.")

        return reasons
