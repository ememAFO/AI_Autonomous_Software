from dataclasses import dataclass, field
from enum import StrEnum

from src.research.industry_taxonomy import IndustryCategory


class SourceType(StrEnum):
    REDDIT = "reddit"
    GITHUB_ISSUES = "github_issues"
    PRODUCT_HUNT = "product_hunt"
    G2 = "g2"
    CAPTERRA = "capterra"
    TRUSTPILOT = "trustpilot"
    HACKER_NEWS = "hacker_news"
    INDIE_HACKERS = "indie_hackers"
    BETALIST = "betalist"
    SAAS_DIRECTORY = "saas_directory"
    REVIEW_SITE = "review_site"
    SUPPORT_FORUM = "support_forum"
    JOB_POSTINGS = "job_postings"


@dataclass(frozen=True)
class ResearchSource:
    source_type: SourceType
    name: str
    description: str
    industries: set[IndustryCategory]
    allowed: bool = True
    requires_api: bool = False
    max_results_per_run: int = 25
    blocked_reason: str | None = None
    keywords: list[str] = field(default_factory=list)


class SourceCatalog:
    """
    Controlled source catalog.

    Purpose:
    - define where research can come from
    - keep future adapters policy-aware
    - separate allowed public research sources from blocked/private sources
    """

    def __init__(self):
        self._sources = self._build_sources()

    def list_sources(self) -> list[ResearchSource]:
        return self._sources

    def allowed_sources(self) -> list[ResearchSource]:
        return [source for source in self._sources if source.allowed]

    def sources_for_industry(
        self,
        industry: IndustryCategory,
    ) -> list[ResearchSource]:
        return [
            source
            for source in self.allowed_sources()
            if industry in source.industries
        ]

    def sources_for_type(
        self,
        source_type: SourceType,
    ) -> list[ResearchSource]:
        return [
            source
            for source in self._sources
            if source.source_type == source_type
        ]

    def _build_sources(self) -> list[ResearchSource]:
        return [
            ResearchSource(
                source_type=SourceType.REDDIT,
                name="Public Reddit research",
                description="Public subreddit posts used for pain-point discovery.",
                industries={
                    IndustryCategory.SALES,
                    IndustryCategory.SAAS,
                    IndustryCategory.HEALTHCARE,
                    IndustryCategory.ACCOUNTING,
                    IndustryCategory.REAL_ESTATE,
                    IndustryCategory.RECRUITMENT,
                    IndustryCategory.HOME_SERVICES,
                    IndustryCategory.ECOMMERCE,
                    IndustryCategory.CUSTOMER_SUPPORT,
                },
                allowed=True,
                requires_api=False,
                max_results_per_run=25,
                keywords=[
                    "manual work",
                    "too expensive",
                    "missing feature",
                    "clients stop replying",
                    "lost leads",
                ],
            ),
            ResearchSource(
                source_type=SourceType.PRODUCT_HUNT,
                name="Product Hunt launches",
                description="New SaaS and AI product launches for trend discovery.",
                industries={
                    IndustryCategory.SAAS,
                    IndustryCategory.SALES,
                    IndustryCategory.MARKETING,
                    IndustryCategory.CUSTOMER_SUPPORT,
                    IndustryCategory.ECOMMERCE,
                },
                allowed=True,
                requires_api=True,
                max_results_per_run=20,
                keywords=[
                    "new SaaS",
                    "AI tools",
                    "launch",
                    "startup",
                    "alternative",
                ],
            ),
            ResearchSource(
                source_type=SourceType.G2,
                name="G2 review complaints",
                description="Public review patterns and competitor weaknesses.",
                industries={
                    IndustryCategory.SAAS,
                    IndustryCategory.SALES,
                    IndustryCategory.MARKETING,
                    IndustryCategory.CUSTOMER_SUPPORT,
                    IndustryCategory.ACCOUNTING,
                    IndustryCategory.RECRUITMENT,
                },
                allowed=True,
                requires_api=False,
                max_results_per_run=20,
                keywords=[
                    "missing integration",
                    "too expensive",
                    "poor support",
                    "hard to use",
                ],
            ),
            ResearchSource(
                source_type=SourceType.CAPTERRA,
                name="Capterra software reviews",
                description="Software reviews for pain-point and competitor gap analysis.",
                industries={
                    IndustryCategory.SAAS,
                    IndustryCategory.ACCOUNTING,
                    IndustryCategory.REAL_ESTATE,
                    IndustryCategory.HEALTHCARE,
                    IndustryCategory.CUSTOMER_SUPPORT,
                },
                allowed=True,
                requires_api=False,
                max_results_per_run=20,
                keywords=[
                    "software review",
                    "competitor complaint",
                    "feature request",
                    "workflow pain",
                ],
            ),
            ResearchSource(
                source_type=SourceType.GITHUB_ISSUES,
                name="GitHub public issues",
                description="Public open-source issues used to detect technical workflow pain.",
                industries={
                    IndustryCategory.SAAS,
                    IndustryCategory.CUSTOMER_SUPPORT,
                    IndustryCategory.SAAS,
                },
                allowed=True,
                requires_api=True,
                max_results_per_run=25,
                keywords=[
                    "bug",
                    "feature request",
                    "integration issue",
                    "workflow broken",
                ],
            ),
            ResearchSource(
                source_type=SourceType.JOB_POSTINGS,
                name="Public job postings",
                description="Job descriptions used to detect repetitive workflows companies are hiring for.",
                industries={
                    IndustryCategory.SALES,
                    IndustryCategory.HEALTHCARE,
                    IndustryCategory.ACCOUNTING,
                    IndustryCategory.RECRUITMENT,
                    IndustryCategory.CUSTOMER_SUPPORT,
                },
                allowed=True,
                requires_api=False,
                max_results_per_run=20,
                keywords=[
                    "manual reporting",
                    "CRM admin",
                    "data entry",
                    "workflow coordination",
                ],
            ),
            ResearchSource(
                source_type=SourceType.SUPPORT_FORUM,
                name="Private or login-only support forums",
                description="Blocked unless explicit permission and terms allow access.",
                industries=set(IndustryCategory),
                allowed=False,
                requires_api=False,
                max_results_per_run=0,
                blocked_reason="Do not access private or login-only communities without permission.",
            ),
        ]
