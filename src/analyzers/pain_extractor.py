from dataclasses import dataclass


@dataclass(frozen=True)
class PainSignal:
    text: str
    matched_terms: list[str]
    frustration_score: float
    is_business_pain: bool


class PainExtractor:
    """
    Detects business pain signals from raw text.

    This is intentionally simple for v1:
    - no external API
    - no uncontrolled browsing
    - easy to test
    - easy to improve later with Hermes or embeddings
    """

    PAIN_TERMS = [
        "frustrated",
        "annoying",
        "waste time",
        "manual",
        "too expensive",
        "missing",
        "doesn't work",
        "does not work",
        "hard to manage",
        "keep forgetting",
        "losing leads",
        "missed booking",
        "missed bookings",
        "no show",
        "no-shows",
        "follow up",
        "follow-up",
        "customers stop replying",
        "clients stop replying",
        "takes too long",
        "repetitive",
        "spreadsheet",
        "can't track",
        "cannot track",
        "overwhelmed",
        "chasing clients",
        "chasing customers",
        "lost revenue",
    ]

    BUSINESS_TERMS = [
        "client",
        "clients",
        "customer",
        "customers",
        "lead",
        "leads",
        "booking",
        "bookings",
        "quote",
        "quotes",
        "invoice",
        "invoices",
        "appointment",
        "appointments",
        "business",
        "sales",
        "revenue",
        "staff",
        "team",
        "workflow",
        "crm",
        "support",
    ]

    def extract(self, text: str) -> PainSignal:
        if not text or not text.strip():
            return PainSignal(
                text=text,
                matched_terms=[],
                frustration_score=0.0,
                is_business_pain=False,
            )

        normalized_text = text.lower()

        matched_pain_terms = [
            term for term in self.PAIN_TERMS if term in normalized_text
        ]

        matched_business_terms = [
            term for term in self.BUSINESS_TERMS if term in normalized_text
        ]

        frustration_score = self._calculate_frustration_score(
            matched_pain_terms=matched_pain_terms,
            matched_business_terms=matched_business_terms,
        )

        is_business_pain = bool(matched_pain_terms) and bool(matched_business_terms)

        return PainSignal(
            text=text,
            matched_terms=matched_pain_terms + matched_business_terms,
            frustration_score=frustration_score,
            is_business_pain=is_business_pain,
        )

    def extract_many(self, texts: list[str]) -> list[PainSignal]:
        return [self.extract(text) for text in texts]

    def _calculate_frustration_score(
        self,
        matched_pain_terms: list[str],
        matched_business_terms: list[str],
    ) -> float:
        score = 0.0

        score += min(len(matched_pain_terms) * 1.5, 7.0)
        score += min(len(matched_business_terms) * 0.5, 3.0)

        return round(min(score, 10.0), 2)
