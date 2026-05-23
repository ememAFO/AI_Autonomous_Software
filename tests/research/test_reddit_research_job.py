import pytest

from src.adapters.reddit_fetcher import (
    RedditFetcherConfig,
    RedditFetcherError,
    RedditResearchQuery,
    SafeRedditFetcher,
)
from src.research.reddit_research_job import RedditResearchJob


def test_reddit_research_job_runs_fetcher_adapter_and_pipeline():
    job = RedditResearchJob()

    result = job.run(
        research_query=RedditResearchQuery(
            query="manual follow up",
            subreddit="smallbusiness",
            limit=2,
        ),
        industry="home services",
    )

    assert result.processed_count == 2
    assert result.accepted_count >= 1
    assert result.rejected_count >= 0
    assert result.query.subreddit == "smallbusiness"

    for pipeline_result in result.adapter_result.results:
        assert pipeline_result.report_path.exists()


def test_reddit_research_job_blocks_empty_industry():
    job = RedditResearchJob()

    with pytest.raises(ValueError):
        job.run(
            research_query=RedditResearchQuery(
                query="manual follow up",
                subreddit="smallbusiness",
                limit=2,
            ),
            industry="",
        )


def test_reddit_research_job_respects_fetcher_subreddit_policy():
    fetcher = SafeRedditFetcher(
        config=RedditFetcherConfig(
            allowed_subreddits={"smallbusiness"},
        )
    )

    job = RedditResearchJob(fetcher=fetcher)

    with pytest.raises(RedditFetcherError):
        job.run(
            research_query=RedditResearchQuery(
                query="manual follow up",
                subreddit="unknowncommunity",
                limit=2,
            ),
            industry="home services",
        )


def test_reddit_research_job_respects_fetcher_limit_policy():
    fetcher = SafeRedditFetcher(
        config=RedditFetcherConfig(
            max_results_per_query=1,
        )
    )

    job = RedditResearchJob(fetcher=fetcher)

    with pytest.raises(RedditFetcherError):
        job.run(
            research_query=RedditResearchQuery(
                query="manual follow up",
                subreddit="smallbusiness",
                limit=2,
            ),
            industry="home services",
        )


def test_reddit_research_job_generates_opportunity_reports():
    job = RedditResearchJob()

    result = job.run(
        research_query=RedditResearchQuery(
            query="missed bookings",
            subreddit="smallbusiness",
            limit=2,
        ),
        industry="clinics",
    )

    assert result.accepted_count >= 1

    report_paths = [
        pipeline_result.report_path
        for pipeline_result in result.adapter_result.results
    ]

    assert report_paths

    for report_path in report_paths:
        assert report_path.exists()
        assert str(report_path).endswith(".md")
