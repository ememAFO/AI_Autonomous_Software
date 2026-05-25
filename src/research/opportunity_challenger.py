from dataclasses import dataclass, field
from enum import StrEnum

from src.research.models import Opportunity


class ProblemType(StrEnum):
    WORKFLOW_FAILURE = "workflow_failure"
    COMMUNICATION_FAILURE = "communication_failure"
    AUTOMATION_GAP = "automation_gap"
    UX_ISSUE = "ux_issue"
    TRAINING_ISSUE = "training_issue"
    COMPLIANCE_ISSUE = "compliance_issue"
    UNCLEAR = "unclear"


class ChallengeRecommendation(StrEnum):
    CONTINUE_TO_SCORING = "CONTINUE_TO_SCORING"
    VALIDATE_BEFORE_SCORING = "VALIDATE_BEFORE_SCORING"
    REFRAME_OPPORTUNITY = "REFRAME_OPPORTUNITY"
    REJECT_FALSE_OPPORTUNITY = "REJECT_FALSE_OPPORTUNITY"


@dataclass(frozen=True)
class OpportunityChallengeResult:
    should_continue: bool
    problem_type: ProblemType
    recommendation: ChallengeRecommendation
    reframed_problem: str
    hidden_assumptions: list[str] = field(default_factory=list)
    false_opportunity_risks: list[str] = field(default_factory=list)
    validation_questions: list[str] = field(default_factory=list)


class OpportunityChallenger:
    """
    Strategic validation layer.

    Purpose:
    - challenge weak opportunity framing
    - detect false opportunities
    - identify hidden assumptions
    - reframe symptoms into higher-value business problems

    This module does not:
    - fetch external data
    - write files
    - execute commands
    - deploy anything
    """

    LOW_COMMERCIAL_SIGNAL_TERMS = {
        "colour",
        "color",
        "theme",
        "font",
        "nice to have",
        "cosmetic",
        "minor",
    }

    ECONOMIC_SIGNAL_TERMS = {
        "revenue",
        "sales",
        "leads",
        "lost deals",
        "quotes",
        "invoice",
        "invoices",
        "payments",
        "customers",
        "clients",
        "bookings",
        "appointments",
        "churn",
        "retention",
    }

    WORKFLOW_TERMS = {
        "manual",
        "spreadsheet",
        "repetitive",
        "takes too long",
        "follow up",
        "follow-up",
        "chasing",
        "track",
        "workflow",
    }

    COMMUNICATION_TERMS = {
        "replying",
        "responding",
        "messages",
        "email",
        "call",
        "reminder",
        "follow up",
        "follow-up",
    }

    UX_TERMS = {
        "confusing",
        "hard to use",
        "annoying",
        "clunky",
        "dashboard",
        "interface",
    }

    TRAINING_TERMS = {
        "do not know how",
        "don't know how",
        "training",
        "onboarding",
        "learn",
        "tutorial",
    }

    COMPLIANCE_TERMS = {
        "compliance",
        "audit",
        "regulation",
        "policy",
        "legal requirement",
    }

    def challenge(self, opportunity: Opportunity) -> OpportunityChallengeResult:
        text = self._combined_text(opportunity)

        problem_type = self._classify_problem_type(text)
        false_risks = self._detect_false_opportunity_risks(opportunity, text)
        assumptions = self._hidden_assumptions(opportunity, text)
        reframed_problem = self._reframe(opportunity, problem_type, text)
        validation_questions = self._validation_questions(opportunity, problem_type)

        recommendation = self._recommend(
            opportunity=opportunity,
            problem_type=problem_type,
            false_risks=false_risks,
            text=text,
        )

        should_continue = recommendation in {
            ChallengeRecommendation.CONTINUE_TO_SCORING,
            ChallengeRecommendation.VALIDATE_BEFORE_SCORING,
            ChallengeRecommendation.REFRAME_OPPORTUNITY,
        }

        return OpportunityChallengeResult(
            should_continue=should_continue,
            problem_type=problem_type,
            recommendation=recommendation,
            reframed_problem=reframed_problem,
            hidden_assumptions=assumptions,
            false_opportunity_risks=false_risks,
            validation_questions=validation_questions,
        )

    def _combined_text(self, opportunity: Opportunity) -> str:
        return " ".join(
            [
                opportunity.title,
                opportunity.pain_point,
                opportunity.industry,
                opportunity.suggested_mvp or "",
                *opportunity.evidence,
            ]
        ).lower()

    def _classify_problem_type(self, text: str) -> ProblemType:
        if self._contains_any(text, self.COMPLIANCE_TERMS):
            return ProblemType.COMPLIANCE_ISSUE

        if self._contains_any(text, self.WORKFLOW_TERMS):
            return ProblemType.WORKFLOW_FAILURE

        if self._contains_any(text, self.COMMUNICATION_TERMS):
            return ProblemType.COMMUNICATION_FAILURE

        if self._contains_any(text, self.TRAINING_TERMS):
            return ProblemType.TRAINING_ISSUE

        if self._contains_any(text, self.UX_TERMS):
            return ProblemType.UX_ISSUE

        return ProblemType.UNCLEAR

    def _detect_false_opportunity_risks(
        self,
        opportunity: Opportunity,
        text: str,
    ) -> list[str]:
        risks: list[str] = []

        if self._contains_any(text, self.LOW_COMMERCIAL_SIGNAL_TERMS):
            risks.append(
                "The complaint may be cosmetic or low-value rather than a strong business pain."
            )

        if not self._has_valid_economic_signal(text):
            risks.append(
                "There is weak evidence of economic loss or willingness to pay."
            )

        if opportunity.frequency < 4:
            risks.append(
                "The pain appears too infrequent to justify building yet."
            )

        if opportunity.monetization < 4:
            risks.append(
                "The monetization signal is weak."
            )

        if opportunity.implementation_difficulty >= 8 and opportunity.monetization < 8:
            risks.append(
                "Implementation difficulty may be too high compared with commercial value."
            )

        if opportunity.automation_potential < 4:
            risks.append(
                "Automation may not solve the underlying problem."
            )

        return risks

    def _hidden_assumptions(
        self,
        opportunity: Opportunity,
        text: str,
    ) -> list[str]:
        assumptions = [
            "Users will pay to solve this problem specifically.",
            "The stated complaint is the root cause, not only a symptom.",
            "Automation is better than process improvement or training.",
        ]

        if "crm" in text:
            assumptions.append(
                "The issue is caused by CRM workflow friction rather than poor sales discipline."
            )

        if "follow up" in text or "follow-up" in text:
            assumptions.append(
                "Users lose value because follow-up is slow or forgotten."
            )

        if "booking" in text or "appointment" in text:
            assumptions.append(
                "Missed bookings are caused by workflow gaps rather than demand quality."
            )

        if opportunity.implementation_difficulty >= 7:
            assumptions.append(
                "The MVP can be reduced enough to avoid overengineering."
            )

        return assumptions

    def _reframe(
        self,
        opportunity: Opportunity,
        problem_type: ProblemType,
        text: str,
    ) -> str:
        if "lead" in text or "quote" in text or "sales" in text:
            return "Revenue leakage caused by slow or inconsistent lead follow-up."

        if "booking" in text or "appointment" in text or "no-show" in text:
            return "Operational revenue loss caused by missed bookings, weak reminders, or poor appointment recovery."

        if "invoice" in text or "payment" in text:
            return "Cash-flow delay caused by manual invoice chasing and weak payment follow-up."

        if problem_type == ProblemType.UX_ISSUE:
            return "Possible usability friction, but commercial urgency must be proven before building."

        if problem_type == ProblemType.TRAINING_ISSUE:
            return "Possible onboarding or training gap rather than a standalone SaaS opportunity."

        return opportunity.pain_point

    def _validation_questions(
        self,
        opportunity: Opportunity,
        problem_type: ProblemType,
    ) -> list[str]:
        return [
            "Is this the real underlying problem or only a symptom?",
            "What economic loss does this create?",
            "Are users already paying, hiring, or using manual workarounds to solve it?",
            "How often does the problem occur?",
            "Would eliminating the workflow be better than automating it?",
            f"Is this best understood as a {problem_type.value}?",
            "What is the smallest MVP that proves willingness to pay?",
            "What evidence would make this opportunity invalid?",
        ]

    def _recommend(
        self,
        opportunity: Opportunity,
        problem_type: ProblemType,
        false_risks: list[str],
        text: str,
    ) -> ChallengeRecommendation:
        if (
            self._contains_any(text, self.LOW_COMMERCIAL_SIGNAL_TERMS)
            and not self._has_valid_economic_signal(text)
        ):
            return ChallengeRecommendation.REJECT_FALSE_OPPORTUNITY

        if len(false_risks) >= 3:
            return ChallengeRecommendation.REJECT_FALSE_OPPORTUNITY

        if problem_type in {ProblemType.UNCLEAR, ProblemType.UX_ISSUE, ProblemType.TRAINING_ISSUE}:
            return ChallengeRecommendation.VALIDATE_BEFORE_SCORING

        if opportunity.implementation_difficulty >= 7:
            return ChallengeRecommendation.REFRAME_OPPORTUNITY

        if false_risks:
            return ChallengeRecommendation.VALIDATE_BEFORE_SCORING

        return ChallengeRecommendation.CONTINUE_TO_SCORING
    def _has_valid_economic_signal(self, text: str) -> bool:
        negated_economic_phrases = {
            "no revenue issue",
            "no revenue impact",
            "not affecting revenue",
            "does not affect revenue",
            "doesn't affect revenue",
            "no sales impact",
            "not affecting sales",
            "no lost deals",
            "no payment issue",
            "no customer loss",
            "no client loss",
        }

        if self._contains_any(text, negated_economic_phrases):
            return False

        return self._contains_any(text, self.ECONOMIC_SIGNAL_TERMS)

    def _contains_any(self, text: str, terms: set[str]) -> bool:
        return any(term in text for term in terms)
