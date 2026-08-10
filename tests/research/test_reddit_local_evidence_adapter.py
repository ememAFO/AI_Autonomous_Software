from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest

from src.adapters.reddit_adapter import RedditPost
from src.adapters.reddit_local_evidence_adapter import (
    RedditLocalEvidenceAdapter,
    RedditLocalEvidenceAdapterError,
)
from src.adapters.research_adapter import CandidateStatus


@dataclass(frozen=True)
class FakePipelineResult:
    report_path: Path


@dataclass(frozen=True)
class FakeAdapterResult:
    processed_count: int
    accepted_count: int
    rejected_count: int
    results: list[FakePipelineResult]


class FakeRedditAdapter:
    def __init__(self, *, accepted: bool = True) -> None:
        self.accepted = accepted

    def process_posts(self, *, posts, industry):
        assert industry == "home services"
        assert len(posts) == 1
        return FakeAdapterResult(
            processed_count=1,
            accepted_count=1 if self.accepted else 0,
            rejected_count=0 if self.accepted else 1,
            results=[FakePipelineResult(Path("reports/reddit.md"))]
            if self.accepted
            else [],
        )


def test_supplied_public_post_becomes_candidate() -> None:
    adapter = RedditLocalEvidenceAdapter(FakeRedditAdapter())
    result = adapter.process_post(
        workflow_id="WF-1",
        requested_url=(
            "https://www.reddit.com/r/smallbusiness/comments/abc/post/"
        ),
        post=RedditPost(
            subreddit="smallbusiness",
            title="Quote follow up",
            body="Customers stop replying after quotes.",
            url=(
                "https://www.reddit.com/r/smallbusiness/comments/abc/post/"
            ),
        ),
        industry="home services",
    )
    assert result.candidate is not None
    assert result.candidate.status is CandidateStatus.CANDIDATE
    assert result.candidate.fetcher_used == "supplied_public_post"
    assert result.candidate.raw_metadata["network_fetch_performed"] is False


def test_rejected_reddit_post_does_not_create_candidate() -> None:
    adapter = RedditLocalEvidenceAdapter(
        FakeRedditAdapter(accepted=False)
    )
    result = adapter.process_post(
        workflow_id="WF-1",
        requested_url="https://reddit.com/r/smallbusiness/x/",
        post=RedditPost(
            subreddit="smallbusiness",
            title="Colour preference",
            body="I like blue.",
            url="https://reddit.com/r/smallbusiness/x/",
        ),
        industry="home services",
    )
    assert result.candidate is None
    assert result.reason == "reddit_post_rejected_by_existing_pipeline"


def test_non_reddit_post_url_is_blocked() -> None:
    adapter = RedditLocalEvidenceAdapter(FakeRedditAdapter())
    with pytest.raises(RedditLocalEvidenceAdapterError):
        adapter.process_post(
            workflow_id="WF-1",
            requested_url="https://example.com/post",
            post=RedditPost(
                subreddit="smallbusiness",
                title="Quote follow up",
                body="Customers stop replying.",
                url="https://example.com/post",
            ),
            industry="home services",
        )
