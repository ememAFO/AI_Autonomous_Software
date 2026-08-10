from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from src.adapters.reddit_adapter import RedditPost
from src.adapters.reddit_local_evidence_adapter import (
    RedditLocalEvidenceResult,
)
from src.adapters.research_adapter import (
    CandidateStatus,
    EvidenceCandidate,
)
from src.research.research_adapter_router import (
    ResearchAdapterRouter,
    RoutedSourceRequest,
    RouteStatus,
    RouteTarget,
)


def candidate(
    *,
    status: CandidateStatus = CandidateStatus.CANDIDATE,
) -> EvidenceCandidate:
    return EvidenceCandidate(
        workflow_id="WF-1",
        adapter_name="hound",
        adapter_version="13.1.0",
        requested_url="https://example.com/a",
        final_url="https://example.com/a",
        canonical_url="https://example.com/a",
        title="Evidence",
        publisher_or_domain="example.com",
        retrieved_at=datetime.now(UTC).isoformat(),
        status=status,
        content_ok=status is not CandidateStatus.FAILED,
        content="public evidence",
        content_hash="abc",
        fetcher_used="http",
        cached=False,
        warnings=("injection",)
        if status is CandidateStatus.QUARANTINED
        else (),
    )


class FakeHoundAdapter:
    def __init__(self, response=None, error=None) -> None:
        self.response = response or candidate()
        self.error = error
        self.requests = []

    def fetch(self, request):
        self.requests.append(request)
        if self.error:
            raise self.error
        return self.response


@dataclass
class FakeCandidateQueue:
    path: Path = Path("data/research/evidence_candidates/WF-1.jsonl")

    def __post_init__(self):
        self.items = []

    def append(self, *, source_id, candidate):
        self.items.append((source_id, candidate))
        return self.path


@dataclass
class FakeReviewQueue:
    path: Path = Path("data/research/routing_review/WF-1.jsonl")

    def __post_init__(self):
        self.items = []

    def append(self, record):
        self.items.append(record)
        return self.path


class FakeRedditEvidenceAdapter:
    def __init__(self, result):
        self.result = result
        self.calls = []

    def process_post(self, **kwargs):
        self.calls.append(kwargs)
        return self.result


def make_router(
    *,
    hound=None,
    reddit=None,
):
    candidate_queue = FakeCandidateQueue()
    review_queue = FakeReviewQueue()
    router = ResearchAdapterRouter(
        hound_adapter=hound or FakeHoundAdapter(),
        reddit_adapter=reddit,
        candidate_queue=candidate_queue,
        review_queue=review_queue,
    )
    return router, candidate_queue, review_queue


def test_public_known_url_routes_to_hound_candidate_queue() -> None:
    router, candidate_queue, review_queue = make_router()
    result = router.route(
        RoutedSourceRequest(
            workflow_id="WF-1",
            source_id="EV-1",
            url="https://example.com/a",
            focus="claim",
        )
    )
    assert result.target is RouteTarget.HOUND
    assert result.status is RouteStatus.QUEUED
    assert len(candidate_queue.items) == 1
    assert not review_queue.items


def test_hound_failure_routes_to_human_review() -> None:
    router, candidate_queue, review_queue = make_router(
        hound=FakeHoundAdapter(error=RuntimeError("network failure"))
    )
    result = router.route(
        RoutedSourceRequest(
            workflow_id="WF-1",
            source_id="EV-2",
            url="https://example.com/b",
        )
    )
    assert result.target is RouteTarget.HUMAN_REVIEW
    assert result.status is RouteStatus.REVIEW_REQUIRED
    assert not candidate_queue.items
    assert len(review_queue.items) == 1


def test_quarantined_hound_candidate_is_queued_and_reviewed() -> None:
    router, candidate_queue, review_queue = make_router(
        hound=FakeHoundAdapter(
            response=candidate(status=CandidateStatus.QUARANTINED)
        )
    )
    result = router.route(
        RoutedSourceRequest(
            workflow_id="WF-1",
            source_id="EV-3",
            url="https://example.com/c",
        )
    )
    assert result.status is RouteStatus.QUARANTINED
    assert len(candidate_queue.items) == 1
    assert len(review_queue.items) == 1


def test_live_reddit_url_goes_to_review_not_hound() -> None:
    hound = FakeHoundAdapter()
    router, candidate_queue, review_queue = make_router(hound=hound)
    result = router.route(
        RoutedSourceRequest(
            workflow_id="WF-1",
            source_id="EV-R",
            url=(
                "https://www.reddit.com/r/electricians/comments/x/post/"
            ),
            industry="home services",
        )
    )
    assert result.target is RouteTarget.HUMAN_REVIEW
    assert result.reason == "live_reddit_url_fetch_not_supported"
    assert not hound.requests
    assert not candidate_queue.items
    assert len(review_queue.items) == 1


def test_supplied_reddit_post_routes_through_local_adapter() -> None:
    reddit_candidate = candidate()
    reddit_candidate = EvidenceCandidate(
        **{
            **reddit_candidate.__dict__,
            "adapter_name": "reddit-local",
            "requested_url": "https://reddit.com/r/smallbusiness/x/",
            "final_url": "https://reddit.com/r/smallbusiness/x/",
            "canonical_url": "https://reddit.com/r/smallbusiness/x/",
        }
    )
    reddit = FakeRedditEvidenceAdapter(
        RedditLocalEvidenceResult(
            candidate=reddit_candidate,
            processed_count=1,
            accepted_count=1,
            rejected_count=0,
            report_paths=("reports/reddit.md",),
            reason="reddit_post_accepted_by_existing_pipeline",
        )
    )
    hound = FakeHoundAdapter()
    router, candidate_queue, review_queue = make_router(
        hound=hound,
        reddit=reddit,
    )
    result = router.route(
        RoutedSourceRequest(
            workflow_id="WF-1",
            source_id="EV-R",
            url="https://reddit.com/r/smallbusiness/x/",
            industry="home services",
            reddit_post=RedditPost(
                subreddit="smallbusiness",
                title="Quote follow up",
                body="Customers stop replying.",
                url="https://reddit.com/r/smallbusiness/x/",
            ),
        )
    )
    assert result.target is RouteTarget.REDDIT_LOCAL
    assert result.status is RouteStatus.QUEUED
    assert not hound.requests
    assert len(candidate_queue.items) == 1
    assert not review_queue.items


def test_invalid_scheme_is_blocked_before_adapter_call() -> None:
    hound = FakeHoundAdapter()
    router, candidate_queue, review_queue = make_router(hound=hound)
    result = router.route(
        RoutedSourceRequest(
            workflow_id="WF-1",
            source_id="EV-X",
            url="file:///etc/passwd",
        )
    )
    assert result.target is RouteTarget.BLOCKED
    assert result.status is RouteStatus.BLOCKED
    assert not hound.requests
    assert not candidate_queue.items
    assert len(review_queue.items) == 1
