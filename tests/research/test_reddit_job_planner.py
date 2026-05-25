import pytest

from src.research.industry_taxonomy import IndustryCategory
from src.research.reddit_job_planner import (
    RedditJobPlanner,
    RedditJobPlannerError,
)
from src.research.source_catalog import SourceType


def test_reddit_job_planner_creates_sales_jobs():
    planner = RedditJobPlanner()

    plan = planner.plan_for_industry(
        industry=IndustryCategory.SALES,
        limit_per_job=5,
    )

    assert plan.industry == IndustryCategory.SALES
    assert plan.jobs

    first_job = plan.jobs[0]

    assert first_job.industry == IndustryCategory.SALES
    assert first_job.query.query == "sales follow up"
    assert first_job.query.subreddit in {"smallbusiness", "entrepreneur"}
    assert first_job.query.limit == 5


def test_reddit_job_planner_creates_saas_jobs():
    planner = RedditJobPlanner()

    plan = planner.plan_for_industry(
        industry=IndustryCategory.SAAS,
        limit_per_job=3,
    )

    assert plan.industry == IndustryCategory.SAAS
    assert plan.jobs

    subreddits = {job.query.subreddit for job in plan.jobs}

    assert "SaaS" in subreddits
    assert "entrepreneur" in subreddits


def test_reddit_job_planner_limits_jobs_per_plan():
    planner = RedditJobPlanner()

    plan = planner.plan_for_industry(
        industry=IndustryCategory.SALES,
        limit_per_job=5,
    )

    assert len(plan.jobs) <= planner.MAX_JOBS_PER_PLAN
    assert "Maximum jobs per plan reached." in plan.skipped_reasons


def test_reddit_job_planner_blocks_empty_industry_text():
    planner = RedditJobPlanner()

    with pytest.raises(RedditJobPlannerError):
        planner.plan_from_text("")


def test_reddit_job_planner_blocks_unknown_industry():
    planner = RedditJobPlanner()

    with pytest.raises(RedditJobPlannerError):
        planner.plan_from_text("unknown industry")


def test_reddit_job_planner_blocks_zero_limit():
    planner = RedditJobPlanner()

    with pytest.raises(RedditJobPlannerError):
        planner.plan_for_industry(
            industry=IndustryCategory.SALES,
            limit_per_job=0,
        )


def test_reddit_job_planner_blocks_excessive_limit():
    planner = RedditJobPlanner()

    with pytest.raises(RedditJobPlannerError):
        planner.plan_for_industry(
            industry=IndustryCategory.SALES,
            limit_per_job=100,
        )


def test_reddit_job_planner_plan_from_text_accepts_hyphenated_industry():
    planner = RedditJobPlanner()

    plan = planner.plan_from_text("real-estate", limit_per_job=2)

    assert plan.industry == IndustryCategory.REAL_ESTATE
    assert plan.jobs
    assert all(job.query.limit == 2 for job in plan.jobs)
