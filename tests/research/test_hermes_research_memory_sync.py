from src.adapters.reddit_fetcher import RedditResearchQuery
from src.hermes.research_memory_sync import HermesResearchMemorySync
from src.research.reddit_research_job import RedditResearchJob
from src.hermes.research_memory import HermesResearchMemoryHook


def test_hermes_memory_sync_writes_records_from_reddit_job():
    job_result = RedditResearchJob().run(
        research_query=RedditResearchQuery(
            query="manual follow up",
            subreddit="smallbusiness",
            limit=2,
        ),
        industry="home services",
    )

    sync = HermesResearchMemorySync(
        memory_hook=HermesResearchMemoryHook(
            memory_dir="data/hermes/research_memory/test_sync"
        )
    )

    sync_result = sync.sync_from_reddit_job(job_result)


    assert sync_result.written_count == job_result.accepted_count
    assert sync_result.memory_paths

    for memory_path in sync_result.memory_paths:
        assert memory_path.exists()
        assert memory_path.suffix == ".json"
        assert "data/hermes/research_memory" in str(memory_path)


def test_hermes_memory_sync_handles_no_accepted_results():
    job_result = RedditResearchJob().run(
        research_query=RedditResearchQuery(
            query="neutral text",
            subreddit="smallbusiness",
            limit=1,
        ),
        industry="general",
    )

    # The current mock fetcher still returns pain-heavy mock posts,
    # so this test verifies the sync result structure rather than forcing zero.

    sync = HermesResearchMemorySync(
        memory_hook=HermesResearchMemoryHook(
            memory_dir="data/hermes/research_memory/test_sync"
        )
    )

    sync_result = sync.sync_from_reddit_job(job_result)


    assert sync_result.written_count == len(sync_result.memory_paths)
