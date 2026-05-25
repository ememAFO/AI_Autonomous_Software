from src.research.industry_taxonomy import IndustryCategory
from src.research.planned_reddit_research_runner import (
    PlannedRedditResearchRunner,
)
from src.research.reddit_job_planner import (
    PlannedRedditResearchJob,
    RedditJobPlan,
)
from src.adapters.reddit_fetcher import RedditResearchQuery


def test_planned_reddit_research_runner_runs_sales_plan():
    runner = PlannedRedditResearchRunner()

    result = runner.run_for_industry(
        industry_text="sales",
        limit_per_job=2,
    )

    assert result.industry == "sales"
    assert result.planned_count > 0
    assert result.successful_count > 0
    assert result.blocked_count == 0

    first = result.results[0]

    assert first.status == "success"
    assert first.processed_count > 0
    assert first.accepted_count > 0
    assert first.final_workflow_stage == "REPORT"
    assert first.report_paths
    assert first.manifest_path is not None
    assert first.registry_path is not None
    assert first.hermes_memory_count > 0
    assert first.hermes_memory_paths


def test_planned_reddit_research_runner_blocks_unknown_industry():
    runner = PlannedRedditResearchRunner()

    try:
        runner.run_for_industry("unknown", limit_per_job=2)
    except Exception as exc:
        assert "Unsupported industry" in str(exc)
    else:
        raise AssertionError("Expected unsupported industry to be blocked")


def test_planned_reddit_research_runner_records_blocked_job():
    runner = PlannedRedditResearchRunner()

    plan = RedditJobPlan(
        industry=IndustryCategory.SALES,
        jobs=[
            PlannedRedditResearchJob(
                industry=IndustryCategory.SALES,
                query=RedditResearchQuery(
                    query="manual follow up",
                    subreddit="unknowncommunity",
                    limit=2,
                ),
            )
        ],
    )

    result = runner.run_plan(plan)

    assert result.planned_count == 1
    assert result.successful_count == 0
    assert result.blocked_count == 1
    assert result.results[0].status == "blocked"
    assert result.results[0].error is not None


def test_planned_reddit_research_runner_respects_limit_per_job():
    runner = PlannedRedditResearchRunner()

    result = runner.run_for_industry(
        industry_text="saas",
        limit_per_job=1,
    )

    assert result.planned_count > 0

    for job_result in result.results:
        if job_result.status == "success":
            assert job_result.processed_count <= 1
