from dataclasses import dataclass


@dataclass(frozen=True)
class SourceQuality:
    source_quality: str
    evidence_weight: float
    rationale: str


class SourceQualityClassifier:
    """
    Classifies evidence quality for research-memory and trend reporting.

    Purpose:
    - avoid treating all feedback sources equally
    - separate B2B software evidence from consumer/noisy evidence
    - keep source weighting transparent and explainable

    This does not delete or block records.
    It only labels evidence quality for reporting and prioritization.
    """

    def classify(
        self,
        *,
        source: str,
        industry: str,
        report_path: str = "",
        pain_point: str = "",
    ) -> SourceQuality:
        source_text = source.lower().strip()
        industry_text = industry.lower().strip()
        report_text = report_path.lower().strip()
        pain_text = pain_point.lower().strip()

        combined = " ".join(
            [
                source_text,
                industry_text,
                report_text,
                pain_text[:300],
            ]
        )

        if self._is_exploratory_consumer_evidence(combined):
            return SourceQuality(
                source_quality="exploratory_evidence",
                evidence_weight=0.35,
                rationale="Consumer/noisy feedback source. Useful for stress-testing but weak for B2B SaaS opportunity prioritization.",
            )

        if self._is_issue_tracker_evidence(combined):
            return SourceQuality(
                source_quality="core_evidence_issue_tracker",
                evidence_weight=1.0,
                rationale="Issue tracker evidence is useful for bugs, feature gaps, documentation pain, and developer workflow problems.",
            )

        if self._is_core_b2b_software_evidence(source_text + " " + report_text + " " + pain_text[:300]):
            return SourceQuality(
                source_quality="core_evidence",
                evidence_weight=1.0,
                rationale="B2B/software/workflow source with strong relevance to SaaS opportunity discovery.",
            )

        if self._is_supporting_software_evidence(combined):
            return SourceQuality(
                source_quality="supporting_evidence",
                evidence_weight=0.75,
                rationale="Software or app feedback source with useful signals but weaker B2B validation strength than G2/Capterra/TrustRadius.",
            )

        if self._is_operational_service_evidence(combined):
            return SourceQuality(
                source_quality="operational_evidence",
                evidence_weight=0.6,
                rationale="Service/operations review source. Useful for operational pain but less direct for SaaS product opportunity discovery.",
            )

        if self._is_research_or_synthetic_evidence(combined):
            return SourceQuality(
                source_quality="research_or_synthetic_evidence",
                evidence_weight=0.5,
                rationale="Research or synthetic-style source. Useful for exploration, but should not dominate validated product decisions.",
            )

        if industry_text == "saas":
            return SourceQuality(
                source_quality="supporting_evidence",
                evidence_weight=0.75,
                rationale="SaaS-related feedback without a confirmed core B2B review source.",
            )

        return SourceQuality(
            source_quality="unknown_evidence",
            evidence_weight=0.4,
            rationale="Source quality could not be confidently classified.",
        )

    def _is_core_b2b_software_evidence(self, text: str) -> bool:
        return any(
            term in text
            for term in {
                "g2",
                "g2_reviews",
                "capterra",
                "capterra_reviews",
                "trustradius",
                "trustradius_reviews",
                "software product reviews",
                "b2b software",
                "crm",
                "zapier",
                "docusign",
                "hubspot",
                "salesforce",
                "zendesk",
                "intercom",
                "asana",
                "monday",
                "jira",
                "slack",
                "quickbooks",
                "xero",
            }
        )

    def _is_issue_tracker_evidence(self, text: str) -> bool:
        return any(
            term in text
            for term in {
                "github",
                "jira",
                "issue_tracker",
                "issue report",
                "bug report",
                "feature request",
                "documentation issue",
            }
        )

    def _is_supporting_software_evidence(self, text: str) -> bool:
        return any(
            term in text
            for term in {
                "app_store",
                "google_play",
                "chrome extension",
                "wordpress plugin",
                "shopify app",
                "productivity app",
                "business app",
                "developer tool",
            }
        )

    def _is_operational_service_evidence(self, text: str) -> bool:
        return any(
            term in text
            for term in {
                "trustpilot",
                "trustpilot_reviews",
                "airline",
                "united_airlines",
                "travel",
                "delivery",
                "logistics",
                "hotel",
                "restaurant",
                "service review",
            }
        )

    def _is_research_or_synthetic_evidence(self, text: str) -> bool:
        return any(
            term in text
            for term in {
                "reddit",
                "subreddit",
                "synthetic",
                "mock",
                "research_site",
            }
        )

    def _is_exploratory_consumer_evidence(self, text: str) -> bool:
        return any(
            term in text
            for term in {
                "netflix",
                "disney",
                "amazon product",
                "consumer review",
                "entertainment",
                "movie",
                "movies",
                "streaming",
                "theme park",
                "retail",
            }
        )
