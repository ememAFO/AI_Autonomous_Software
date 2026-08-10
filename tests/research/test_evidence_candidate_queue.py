from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from src.adapters.research_adapter import CandidateStatus, EvidenceCandidate
from src.research.evidence_candidate_queue import (
    EvidenceCandidateQueue,
    EvidenceCandidateQueueError,
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
        retrieved_at=datetime.now(timezone.utc).isoformat(),
        status=CandidateStatus.CANDIDATE,
        content_ok=True,
        content="evidence",
        content_hash="abc",
        fetcher_used="http",
        cached=False,
    )


def test_queue_is_append_only_inside_allowed_root(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    queue = EvidenceCandidateQueue()
    path = queue.append(candidate())
    assert path.exists()
    assert len(path.read_text(encoding="utf-8").splitlines()) == 1
    queue.append(candidate())
    assert len(path.read_text(encoding="utf-8").splitlines()) == 2


def test_queue_rejects_path_outside_factory_candidate_area(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    with pytest.raises(EvidenceCandidateQueueError):
        EvidenceCandidateQueue(tmp_path / "reports")
