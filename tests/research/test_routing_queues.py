from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from src.adapters.research_adapter import CandidateStatus, EvidenceCandidate
from src.research.research_routing_review_queue import (
    ResearchRoutingReviewQueue,
    ResearchRoutingReviewQueueError,
    RoutingReviewRecord,
)
from src.research.routed_evidence_candidate_queue import (
    RoutedEvidenceCandidateQueue,
    RoutedEvidenceCandidateQueueError,
)


def candidate() -> EvidenceCandidate:
    return EvidenceCandidate(
        workflow_id="WF-1",
        adapter_name="hound",
        adapter_version="13.1.0",
        requested_url="https://example.com/a",
        final_url="https://example.com/a",
        canonical_url="https://example.com/a",
        title="A",
        publisher_or_domain="example.com",
        retrieved_at=datetime.now(UTC).isoformat(),
        status=CandidateStatus.CANDIDATE,
        content_ok=True,
        content="evidence",
        content_hash="abc",
        fetcher_used="http",
        cached=False,
    )


def test_routed_candidate_queue_is_append_only(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    queue = RoutedEvidenceCandidateQueue()
    path = queue.append(source_id="EV-1", candidate=candidate())
    queue.append(source_id="EV-2", candidate=candidate())
    assert len(path.read_text(encoding="utf-8").splitlines()) == 2


def test_review_queue_is_append_only(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    queue = ResearchRoutingReviewQueue()
    record = RoutingReviewRecord(
        workflow_id="WF-1",
        source_id="EV-1",
        url="https://reddit.com/r/test/x/",
        route_target="human_review",
        reason="live_reddit_url_fetch_not_supported",
    )
    path = queue.append(record)
    queue.append(record)
    assert len(path.read_text(encoding="utf-8").splitlines()) == 2


def test_candidate_queue_rejects_external_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    with pytest.raises(RoutedEvidenceCandidateQueueError):
        RoutedEvidenceCandidateQueue(tmp_path / "reports")


def test_review_queue_rejects_external_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    with pytest.raises(ResearchRoutingReviewQueueError):
        ResearchRoutingReviewQueue(tmp_path / "reports")
