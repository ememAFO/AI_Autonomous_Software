from dataclasses import dataclass, field

from src.adapters.reddit_fetcher import RedditResearchQuery
from src.research.industry_taxonomy import IndustryCategory
from src.research.research_planner import ResearchPlanner, ResearchPlannerError
from src.research.source_catalog import SourceType


class RedditJobPlannerError(Exception):
    pass


@dataclass(frozen=True)
class PlannedRedditResearchJob:
    industry: IndustryCategory
    query: RedditResearchQuery


@dataclass(frozen=True)
class RedditJobPlan:
    industry: IndustryCategory
    jobs: list[PlannedRedditResearchJob]
    skipped_reasons: list[str] = field(default_factory=list)


class RedditJobPlanner:
    """
    Converts an industry research plan into safe Reddit research jobs.

    Security rules:
    - Planning only; no fetching.
    - Uses approved industry taxonomy.
    - Uses approved source catalog.
    - Uses allowlisted subreddits only.
    - Enforces max jobs per plan.
    - Enforces max result limit per job.
    """

    DEFAULT_SUBREDDITS = {
        IndustryCategory.SALES: ["smallbusiness", "entrepreneur"],
        IndustryCategory.SAAS: ["SaaS", "entrepreneur"],
        IndustryCategory.HEALTHCARE: ["smallbusiness"],
        IndustryCategory.CLINICS: ["smallbusiness"],
        IndustryCategory.HOME_SERVICES: ["smallbusiness"],
        IndustryCategory.REAL_ESTATE: ["smallbusiness", "entrepreneur"],
        IndustryCategory.ACCOUNTING: ["smallbusiness", "entrepreneur"],
        IndustryCategory.RECRUITMENT: ["smallbusiness", "entrepreneur"],
        IndustryCategory.ECOMMERCE: ["smallbusiness", "entrepreneur"],
        IndustryCategory.CUSTOMER_SUPPORT: ["SaaS", "smallbusiness"],
    }

    MAX_JOBS_PER_PLAN = 8
    MAX_LIMIT_PER_JOB = 10

    def __init__(self, research_planner: ResearchPlanner | None = None):
        self.research_planner = research_planner or ResearchPlanner()

    def plan_for_industry(
        self,
        industry: IndustryCategory,
        limit_per_job: int = 5,
    ) -> RedditJobPlan:
        self._validate_limit(limit_per_job)

        try:
            research_plan = self.research_planner.plan_for_industry(industry)
        except ResearchPlannerError as exc:
            raise RedditJobPlannerError(str(exc)) from exc

        reddit_sources = [
            source
            for source in research_plan.recommended_sources
            if source.source_type == SourceType.REDDIT and source.allowed
        ]

        if not reddit_sources:
            raise RedditJobPlannerError(
                f"No allowed Reddit research source configured for industry: {industry.value}"
            )

        subreddits = self.DEFAULT_SUBREDDITS.get(industry, ["smallbusiness"])

        jobs: list[PlannedRedditResearchJob] = []
        skipped_reasons: list[str] = []

        for query in research_plan.suggested_queries:
            for subreddit in subreddits:
                if len(jobs) >= self.MAX_JOBS_PER_PLAN:
                    skipped_reasons.append("Maximum jobs per plan reached.")
                    return RedditJobPlan(
                        industry=industry,
                        jobs=jobs,
                        skipped_reasons=list(dict.fromkeys(skipped_reasons)),
                    )

                jobs.append(
                    PlannedRedditResearchJob(
                        industry=industry,
                        query=RedditResearchQuery(
                            query=query,
                            subreddit=subreddit,
                            limit=limit_per_job,
                        ),
                    )
                )

        if not jobs:
            raise RedditJobPlannerError("No Reddit jobs could be planned.")

        return RedditJobPlan(
            industry=industry,
            jobs=jobs,
            skipped_reasons=list(dict.fromkeys(skipped_reasons)),
        )

    def plan_from_text(
        self,
        industry_text: str,
        limit_per_job: int = 5,
    ) -> RedditJobPlan:
        industry = self._parse_industry(industry_text)
        return self.plan_for_industry(
            industry=industry,
            limit_per_job=limit_per_job,
        )

    def _parse_industry(self, industry_text: str) -> IndustryCategory:
        if not industry_text or not industry_text.strip():
            raise RedditJobPlannerError("Industry cannot be empty")

        normalized = industry_text.lower().strip().replace("_", " ").replace("-", " ")

        for industry in IndustryCategory:
            if normalized == industry.value:
                return industry

        supported = ", ".join(sorted(industry.value for industry in IndustryCategory))
        raise RedditJobPlannerError(
            f"Unsupported industry '{industry_text}'. Supported industries: {supported}"
        )

    def _validate_limit(self, limit_per_job: int) -> None:
        if limit_per_job < 1:
            raise RedditJobPlannerError("Limit per job must be at least 1")

        if limit_per_job > self.MAX_LIMIT_PER_JOB:
            raise RedditJobPlannerError(
                f"Limit per job cannot exceed {self.MAX_LIMIT_PER_JOB}"
            )
