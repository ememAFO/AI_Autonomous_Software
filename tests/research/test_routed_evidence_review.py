from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from src.research.routed_evidence_review import (
    ReviewEligibility,
    RoutedEvidenceReviewError,
    RoutedEvidenceReviewService,
)


def candidate(
    *,
    workflow_id: str = "WF-1",
    source_id: str = "EV-1",
    canonical_url: str = "https://example.com/source",
    content: str = "Verified public source content.",
    **overrides,
) -> dict:
    record = {
        "workflow_id": workflow_id,
        "source_id": source_id,
        "adapter_name": "hound",
        "adapter_version": "13.1.0",
        "requested_url": canonical_url,
        "final_url": canonical_url,
        "canonical_url": canonical_url,
        "title": "Evidence",
        "publisher_or_domain": "example.com",
        "retrieved_at": "2026-08-05T00:00:00+00:00",
        "status": "candidate",
        "content_ok": True,
        "content": content,
        "content_hash": hashlib.sha256(
            content.encode("utf-8")
        ).hexdigest(),
        "fetcher_used": "http",
        "cached": False,
        "warnings": [],
        "source_type_hint": "official",
        "official_hint": True,
        "published_date_hint": "",
    }
    record.update(overrides)
    return record


def write_candidates(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    records: list[dict],
) -> Path:
    monkeypatch.chdir(tmp_path)
    path = (
        tmp_path
        / "data"
        / "research"
        / "evidence_candidates"
        / "WF-1.jsonl"
    )
    path.parent.mkdir(parents=True)
    path.write_text(
        "".join(
            json.dumps(record) + "\n"
            for record in records
        ),
        encoding="utf-8",
    )
    return path


def prepare(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    records: list[dict],
):
    path = write_candidates(tmp_path, monkeypatch, records)
    return RoutedEvidenceReviewService().prepare_packet(
        workflow_id="WF-1",
        candidate_file=path,
        output_json=Path(
            "reports/research/evidence_review_packets/WF-1.json"
        ),
        output_markdown=Path(
            "reports/research/evidence_review_packets/WF-1.md"
        ),
        decision_template=Path(
            "reports/research/evidence_review_packets/"
            "WF-1-decision-template.json"
        ),
    )


def test_valid_candidate_is_eligible(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    packet = prepare(
        tmp_path,
        monkeypatch,
        [candidate()],
    )
    assert packet.eligible_candidates == 1
    assert packet.blocked_candidates == 0
    assert (
        packet.items[0].eligibility
        is ReviewEligibility.ELIGIBLE
    )


@pytest.mark.parametrize(
    ("field", "value", "reason"),
    [
        ("cached", True, "cached_content_not_allowed"),
        ("status", "quarantined", "candidate_status_not_reviewable"),
        ("fetcher_used", "stealthy", "fetcher_not_approved"),
        ("content_ok", False, "content_not_ok"),
    ],
)
def test_unsafe_candidate_is_blocked(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    field: str,
    value,
    reason: str,
) -> None:
    packet = prepare(
        tmp_path,
        monkeypatch,
        [candidate(**{field: value})],
    )
    assert packet.blocked_candidates == 1
    assert reason in packet.items[0].blocking_reasons


def test_hash_mismatch_is_blocked(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    packet = prepare(
        tmp_path,
        monkeypatch,
        [candidate(content_hash="bad")],
    )
    assert "content_hash_mismatch" in (
        packet.items[0].blocking_reasons
    )


def test_duplicate_url_and_content_are_blocked(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    packet = prepare(
        tmp_path,
        monkeypatch,
        [
            candidate(source_id="EV-1"),
            candidate(source_id="EV-2"),
        ],
    )
    assert packet.eligible_candidates == 1
    assert packet.blocked_candidates == 1
    assert packet.duplicate_candidates == 1
    assert packet.items[1].duplicate_of_review_id


def test_packet_writes_read_only_review_artifacts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    packet = prepare(
        tmp_path,
        monkeypatch,
        [candidate()],
    )
    root = (
        tmp_path
        / "reports"
        / "research"
        / "evidence_review_packets"
    )
    assert (root / "WF-1.json").exists()
    assert (root / "WF-1.md").exists()
    template = json.loads(
        (root / "WF-1-decision-template.json")
        .read_text(encoding="utf-8")
    )
    assert template["packet_id"] == packet.packet_id
    assert template["decisions"][0]["decision"] == ""


def test_candidate_path_outside_queue_is_rejected(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    path = tmp_path / "outside.jsonl"
    path.write_text(json.dumps(candidate()) + "\n")
    with pytest.raises(RoutedEvidenceReviewError):
        RoutedEvidenceReviewService().prepare_packet(
            workflow_id="WF-1",
            candidate_file=path,
            output_json=Path(
                "reports/research/evidence_review_packets/a.json"
            ),
            output_markdown=Path(
                "reports/research/evidence_review_packets/a.md"
            ),
            decision_template=Path(
                "reports/research/evidence_review_packets/a-template.json"
            ),
        )
