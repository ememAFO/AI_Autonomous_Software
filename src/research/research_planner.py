from dataclasses import dataclass, field

from src.research.industry_taxonomy import (
    IndustryCategory,
    IndustryProfile,
    IndustryTaxonomy,
)
from src.research.source_catalog import ResearchSource, SourceCatalog


class ResearchPlannerError(Exception):
    pass


@dataclass(frozen=True)
class ResearchPlan:
    industry: IndustryCategory
    industry_profile: IndustryProfile
    recommended_sources: list[ResearchSource]
    suggested_queries: list[str]
    blocked_sources: list[ResearchSource] = field(default_factory=list)


class ResearchPlanner:
    """
    Builds controlled research plans for a selected industry.

    Purpose:
    - avoid random browsing
    - use approved industry profiles
    - use approved source catalog
    - generate safe research queries before fetching data
    """

    MAX_QUERIES = 10
    MAX_SOURCES = 6

    def __init__(
        self,
        taxonomy: IndustryTaxonomy | None = None,
        source_catalog: SourceCatalog | None = None,
    ):
        self.taxonomy = taxonomy or IndustryTaxonomy()
        self.source_catalog = source_catalog or SourceCatalog()

    def plan_for_industry(self, industry: IndustryCategory) -> ResearchPlan:
        profile = self.taxonomy.get(industry)

        recommended_sources = self.source_catalog.sources_for_industry(industry)
        blocked_sources = [
            source
            for source in self.source_catalog.list_sources()
            if not source.allowed and industry in source.industries
        ]

        if not recommended_sources:
            raise ResearchPlannerError(
                f"No allowed research sources configured for industry: {industry.value}"
            )

        suggested_queries = self._build_queries(profile=profile)

        return ResearchPlan(
            industry=industry,
            industry_profile=profile,
            recommended_sources=recommended_sources[: self.MAX_SOURCES],
            suggested_queries=suggested_queries[: self.MAX_QUERIES],
            blocked_sources=blocked_sources,
        )

    def plan_from_text(self, industry_text: str) -> ResearchPlan:
        industry = self._parse_industry(industry_text)
        return self.plan_for_industry(industry)

    def _build_queries(self, profile: IndustryProfile) -> list[str]:
        queries: list[str] = []

        queries.extend(profile.research_keywords)

        for pain_theme in profile.pain_themes:
            queries.append(f"{pain_theme} problem")
            queries.append(f"{pain_theme} complaint")

        unique_queries = list(dict.fromkeys(query.strip() for query in queries if query.strip()))

        return unique_queries

    def _parse_industry(self, industry_text: str) -> IndustryCategory:
        if not industry_text or not industry_text.strip():
            raise ResearchPlannerError("Industry cannot be empty")

        normalized = industry_text.lower().strip().replace("_", " ").replace("-", " ")

        for industry in IndustryCategory:
            if normalized == industry.value:
                return industry

        supported = ", ".join(sorted(industry.value for industry in IndustryCategory))
        raise ResearchPlannerError(
            f"Unsupported industry '{industry_text}'. Supported industries: {supported}"
        )
