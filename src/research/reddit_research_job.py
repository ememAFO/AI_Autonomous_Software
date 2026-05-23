from dataclasses import dataclass

from src.adapters.reddit_adapter import RedditAdapter, RedditAdapterResult
from src.adapters.reddit_fetcher import RedditResearchQuery, SafeRedditFetcher


@dataclass(frozen=True)
class RedditResearchJobResult:
    query: RedditResearchQuery
    adapter_result: RedditAdapterResult

    @property
    def processed_count(self) -> int:
        return self.adapter_result.processed_count

    @property
    def accepted_count(self) -> int:
        return self.adapter_result.accepted_count

    @property
    def rejected_count(self) -> int:
        return self.adapter_result.rejected_count


class RedditResearchJob:
    """
    Controlled Reddit research job runner.

    Flow:
    1. Validate and fetch Reddit-style posts using SafeRedditFetcher
    2. Process posts using RedditAdapter
    3. Run accepted posts through the ResearchPipeline
    4. Generate opportunity reports

    Security boundaries:
    - Uses SafeRedditFetcher, which enforces allowed subreddits and result limits.
    - Does not perform live Reddit scraping yet.
    - Does not use credentials.
    - Does not write outside the report generator's safe reports directory.
    - Does not bypass workflow/policy rules.
    """

    def __init__(
        self,
        fetcher: SafeRedditFetcher | None = None,
        adapter: RedditAdapter | None = None,
    ):
        self.fetcher = fetcher or SafeRedditFetcher()
        self.adapter = adapter or RedditAdapter()

    def run(
        self,
        research_query: RedditResearchQuery,
        industry: str,
    ) -> RedditResearchJobResult:
        if not industry or not industry.strip():
            raise ValueError("Industry cannot be empty")

        fetch_result = self.fetcher.fetch(research_query)

        adapter_result = self.adapter.process_posts(
            posts=fetch_result.posts,
            industry=industry,
        )

        return RedditResearchJobResult(
            query=research_query,
            adapter_result=adapter_result,
        )
