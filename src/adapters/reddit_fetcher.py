from dataclasses import dataclass, field

from src.adapters.reddit_adapter import RedditPost


class RedditFetcherError(Exception):
    pass


@dataclass(frozen=True)
class RedditResearchQuery:
    query: str
    subreddit: str
    limit: int = 10


@dataclass(frozen=True)
class RedditFetcherConfig:
    """
    Controls safe Reddit research boundaries.

    This does not perform live Reddit scraping yet.
    It defines the safety rules every future fetcher must obey.
    """

    allowed_subreddits: set[str] = field(
        default_factory=lambda: {
            "smallbusiness",
            "entrepreneur",
            "entrepreneurs",
            "saaS",
            "agency",
            "plumbing",
            "roofing",
            "HVAC",
            "dentistry",
            "salon",
        }
    )
    max_results_per_query: int = 25
    blocked_subreddits: set[str] = field(default_factory=set)


@dataclass(frozen=True)
class RedditFetchResult:
    query: RedditResearchQuery
    posts: list[RedditPost]


class SafeRedditFetcher:
    """
    Safe Reddit fetch layer v2.

    Current version:
    - validates queries
    - enforces subreddit allowlist
    - enforces max result limits
    - blocks private/blocked subreddits
    - returns mocked/local posts only

    Later, this class can be extended to use Reddit API or approved search APIs.
    """

    def __init__(self, config: RedditFetcherConfig | None = None):
        self.config = config or RedditFetcherConfig()

    def fetch(self, research_query: RedditResearchQuery) -> RedditFetchResult:
        self._validate_query(research_query)

        # v2 intentionally returns controlled local data.
        # No live Reddit scraping yet.
        posts = self._mock_posts(research_query)

        return RedditFetchResult(
            query=research_query,
            posts=posts[: research_query.limit],
        )

    def _validate_query(self, research_query: RedditResearchQuery) -> None:
        query = research_query.query.strip()
        subreddit = research_query.subreddit.strip()

        if not query:
            raise RedditFetcherError("Query cannot be empty")

        if not subreddit:
            raise RedditFetcherError("Subreddit cannot be empty")

        if research_query.limit < 1:
            raise RedditFetcherError("Limit must be at least 1")

        if research_query.limit > self.config.max_results_per_query:
            raise RedditFetcherError(
                f"Limit cannot exceed {self.config.max_results_per_query}"
            )

        normalized_subreddit = subreddit.lower()

        allowed = {item.lower() for item in self.config.allowed_subreddits}
        blocked = {item.lower() for item in self.config.blocked_subreddits}

        if normalized_subreddit in blocked:
            raise RedditFetcherError("Subreddit is blocked by policy")

        if normalized_subreddit not in allowed:
            raise RedditFetcherError("Subreddit is not allowed for research")

    def _mock_posts(self, research_query: RedditResearchQuery) -> list[RedditPost]:
        return [
            RedditPost(
                subreddit=research_query.subreddit,
                title="Clients stop replying after quotes",
                body=(
                    "I keep losing leads because manual follow up takes too long "
                    "and customers stop replying after quotes."
                ),
                url="https://reddit.example/mock-1",
            ),
            RedditPost(
                subreddit=research_query.subreddit,
                title="Manual booking is wasting staff time",
                body=(
                    "Our team spends hours on manual appointment booking and "
                    "customers miss bookings when reminders are forgotten."
                ),
                url="https://reddit.example/mock-2",
            ),
        ]
