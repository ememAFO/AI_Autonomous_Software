import pytest

from src.adapters.reddit_fetcher import (
    RedditFetcherConfig,
    RedditFetcherError,
    RedditResearchQuery,
    SafeRedditFetcher,
)


def test_reddit_fetcher_returns_mock_posts_for_allowed_subreddit():
    fetcher = SafeRedditFetcher()

    result = fetcher.fetch(
        RedditResearchQuery(
            query="manual follow up",
            subreddit="smallbusiness",
            limit=2,
        )
    )

    assert result.query.query == "manual follow up"
    assert len(result.posts) == 2
    assert result.posts[0].subreddit == "smallbusiness"


def test_reddit_fetcher_blocks_empty_query():
    fetcher = SafeRedditFetcher()

    with pytest.raises(RedditFetcherError):
        fetcher.fetch(
            RedditResearchQuery(
                query="",
                subreddit="smallbusiness",
                limit=2,
            )
        )


def test_reddit_fetcher_blocks_unapproved_subreddit():
    fetcher = SafeRedditFetcher()

    with pytest.raises(RedditFetcherError):
        fetcher.fetch(
            RedditResearchQuery(
                query="business pain",
                subreddit="randomprivatecommunity",
                limit=2,
            )
        )


def test_reddit_fetcher_blocks_excessive_limit():
    fetcher = SafeRedditFetcher(
        config=RedditFetcherConfig(max_results_per_query=5)
    )

    with pytest.raises(RedditFetcherError):
        fetcher.fetch(
            RedditResearchQuery(
                query="manual work",
                subreddit="smallbusiness",
                limit=6,
            )
        )


def test_reddit_fetcher_blocks_policy_blocked_subreddit():
    fetcher = SafeRedditFetcher(
        config=RedditFetcherConfig(
            blocked_subreddits={"smallbusiness"},
        )
    )

    with pytest.raises(RedditFetcherError):
        fetcher.fetch(
            RedditResearchQuery(
                query="manual work",
                subreddit="smallbusiness",
                limit=2,
            )
        )


def test_reddit_fetcher_blocks_zero_limit():
    fetcher = SafeRedditFetcher()

    with pytest.raises(RedditFetcherError):
        fetcher.fetch(
            RedditResearchQuery(
                query="manual work",
                subreddit="smallbusiness",
                limit=0,
            )
        )
