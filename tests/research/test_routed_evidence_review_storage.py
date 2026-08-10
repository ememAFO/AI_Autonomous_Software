from __future__ import annotations

from pathlib import Path

import pytest

from src.research.routed_evidence_review_storage import (
    EvidenceReviewDecisionRegistry,
    RoutedEvidenceReviewStorageError,
    VerifiedEvidenceIntakeQueue,
)


def verified_payload() -> dict:
    return {
        "workflow_id": "WF-1",
        "review_id": "ER-1",
        "content_hash": "abc",
        "canonical_url": "https://example.com/a",
    }


def test_verified_intake_is_append_only_and_blocks_duplicates(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    queue = VerifiedEvidenceIntakeQueue()
    path = queue.append(verified_payload())
    assert path.exists()
    with pytest.raises(RoutedEvidenceReviewStorageError):
        queue.append(verified_payload())


def test_decision_registry_detects_resolved_packet(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    registry = EvidenceReviewDecisionRegistry()
    registry.append(
        {
            "workflow_id": "WF-1",
            "packet_id": "P-1",
        }
    )
    assert registry.has_packet("P-1") is True
    assert registry.has_packet("P-2") is False


def test_storage_root_outside_controlled_path_is_rejected(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    with pytest.raises(RoutedEvidenceReviewStorageError):
        VerifiedEvidenceIntakeQueue(tmp_path / "outside")
