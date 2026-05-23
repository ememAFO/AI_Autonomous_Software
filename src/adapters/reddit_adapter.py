from dataclasses import dataclass

from src.research.models import OpportunitySource
from src.research.pipeline import PipelineResult, ResearchPipeline


@dataclass(frozen=True)
class RedditPost:
    subreddit: str
    title: str
    body: str
    url: str | None = None

    @property
    def full_text(self) -> str:
        return f"{self.title}\n\n{self.body}".strip()


@dataclass(frozen=True)
class RedditAdapterResult:
    processed_count: int
    accepted_count: int
    rejected_count: int
    results: list[PipelineResult]


class RedditAdapter:
    """
    Local Reddit-style adapter v1.

    This does NOT scrape Reddit yet.

    Security rules:
    - No live web requests.
    - No credentials.
    - No private data access.
    - No uncontrolled loops.
    - Only processes posts provided to it.
    """

    MAX_POSTS_PER_RUN = 50

    def __init__(self, pipeline: ResearchPipeline | None = None):
        self.pipeline = pipeline or ResearchPipeline()

    def process_posts(
        self,
        posts: list[RedditPost],
        industry: str,
    ) -> RedditAdapterResult:
        if len(posts) > self.MAX_POSTS_PER_RUN:
            raise ValueError(f"Too many posts. Limit is {self.MAX_POSTS_PER_RUN} posts per run.")

        results: list[PipelineResult] = []
        rejected_count = 0

        for post in posts:
            try:
                result = self.pipeline.run(
                    raw_text=post.full_text,
                    source=OpportunitySource.REDDIT,
                    industry=industry,
                )
                results.append(result)
            except ValueError:
                rejected_count += 1

        return RedditAdapterResult(
            processed_count=len(posts),
            accepted_count=len(results),
            rejected_count=rejected_count,
            results=results,
        )
