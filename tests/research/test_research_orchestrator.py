import pytest

from src.adapters.reddit_fetcher import RedditFetcherError, RedditResearchQuery
from src.research.research_orchestrator import ResearchOrchestrator
from src.research.workflow_engine import ResearchStage, ResearchWorkflowEngine


def test_research_orchestrator_runs_full_reddit_workflow():
    orchestrator = ResearchOrchestrator()

    result = orchestrator.run_reddit_research(
        research_query=RedditResearchQuery(
            query="manual follow up",
            subreddit="smallbusiness",
            limit=2,
        ),
        industry="home services",
    )

    assert result.final_stage == ResearchStage.REPORT
    assert result.job_result.processed_count == 2
    assert result.job_result.accepted_count >= 1

    for pipeline_result in result.job_result.adapter_result.results:
        assert pipeline_result.report_path.exists()


def test_research_orchestrator_blocks_empty_query():
    orchestrator = ResearchOrchestrator()

    with pytest.raises(ValueError):
        orchestrator.run_reddit_research(
            research_query=RedditResearchQuery(
                query="",
                subreddit="smallbusiness",
                limit=2,
            ),
            industry="home services",
        )


def test_research_orchestrator_blocks_empty_industry():
    orchestrator = ResearchOrchestrator()

    with pytest.raises(ValueError):
        orchestrator.run_reddit_research(
            research_query=RedditResearchQuery(
                query="manual follow up",
                subreddit="smallbusiness",
                limit=2,
            ),
            industry="",
        )


def test_research_orchestrator_respects_fetcher_policy():
    orchestrator = ResearchOrchestrator()

    with pytest.raises(RedditFetcherError):
        orchestrator.run_reddit_research(
            research_query=RedditResearchQuery(
                query="manual follow up",
                subreddit="unknowncommunity",
                limit=2,
            ),
            industry="home services",
        )


def test_research_orchestrator_blocks_stage_skipping():
    workflow_engine = ResearchWorkflowEngine()
    workflow_engine.next_stage(passed=True)

    orchestrator = ResearchOrchestrator(workflow_engine=workflow_engine)

    with pytest.raises(ValueError):
        orchestrator.run_reddit_research(
            research_query=RedditResearchQuery(
                query="manual follow up",
                subreddit="smallbusiness",
                limit=2,
            ),
            industry="home services",
        )
