from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from src.research.routed_evidence_review import (
    RoutedEvidenceReviewError,
    RoutedEvidenceReviewService,
)


def make_candidate() -> dict:
    content = "Official guidance supporting a bounded claim."
    url = "https://example.com/guidance"
    return {
        "workflow_id": "WF-1",
        "source_id": "EV-1",
        "adapter_name": "hound",
        "adapter_version": "13.1.0",
        "requested_url": url,
        "final_url": url,
        "canonical_url": url,
        "title": "Guidance",
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
        "source_type_hint": "regulator",
        "official_hint": True,
        "published_date_hint": "",
    }


def setup_packet(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.chdir(tmp_path)
    candidate_path = (
        tmp_path
        / "data/research/evidence_candidates/WF-1.jsonl"
    )
    candidate_path.parent.mkdir(parents=True)
    candidate_path.write_text(
        json.dumps(make_candidate()) + "\n",
        encoding="utf-8",
    )
    service = RoutedEvidenceReviewService()
    packet = service.prepare_packet(
        workflow_id="WF-1",
        candidate_file=candidate_path,
        output_json=Path(
            "reports/research/evidence_review_packets/WF-1.json"
        ),
        output_markdown=Path(
            "reports/research/evidence_review_packets/WF-1.md"
        ),
        decision_template=Path(
            "reports/research/evidence_review_packets/"
            "WF-1-decisions.json"
        ),
    )
    packet_path = (
        tmp_path
        / "reports/research/evidence_review_packets/WF-1.json"
    )
    decision_path = (
        tmp_path
        / "reports/research/evidence_review_packets/"
        "WF-1-decisions.json"
    )
    return service, packet, packet_path, decision_path


def write_decision(
    path: Path,
    *,
    packet,
    decision: str = "APPROVE",
    reviewer: str = "reviewer-1",
    reason: str = "Source and claim checked.",
    evidence_summary: str = "The source supports the bounded claim.",
    classification: str = "source-verified",
    signal_strength: str = "strong",
    supports_validation=True,
) -> None:
    path.write_text(
        json.dumps(
            {
                "packet_id": packet.packet_id,
                "packet_hash": packet.packet_hash,
                "reviewer_reference": reviewer,
                "decisions": [
                    {
                        "review_id": packet.items[0].review_id,
                        "decision": decision,
                        "reason": reason,
                        "evidence_summary": evidence_summary,
                        "classification": classification,
                        "signal_strength": signal_strength,
                        "supports_validation": supports_validation,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )


def test_approve_promotes_only_to_verified_intake(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service, packet, packet_path, decision_path = (
        setup_packet(tmp_path, monkeypatch)
    )
    write_decision(decision_path, packet=packet)
    result = service.resolve(
        packet_file=packet_path,
        decision_file=decision_path,
        output_path=Path(
            "reports/research/evidence_review_resolutions/"
            "WF-1.json"
        ),
    )
    assert result.approved == 1
    verified = (
        tmp_path
        / "data/research/verified_evidence_intake/WF-1.jsonl"
    )
    assert verified.exists()
    record = json.loads(
        verified.read_text(encoding="utf-8").splitlines()[0]
    )
    assert record["decision"] == "APPROVE"
    assert record["classification"] == "source-verified"
    assert result.protected_actions[
        "validation_evidence_log_modified"
    ] is False


def test_reject_does_not_promote(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service, packet, packet_path, decision_path = (
        setup_packet(tmp_path, monkeypatch)
    )
    write_decision(
        decision_path,
        packet=packet,
        decision="REJECT",
        classification="rejected",
        evidence_summary="",
        signal_strength="",
        supports_validation=None,
    )
    result = service.resolve(
        packet_file=packet_path,
        decision_file=decision_path,
        output_path=Path(
            "reports/research/evidence_review_resolutions/"
            "WF-1.json"
        ),
    )
    assert result.rejected == 1
    assert not (
        tmp_path
        / "data/research/verified_evidence_intake/WF-1.jsonl"
    ).exists()


def test_hold_does_not_promote(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service, packet, packet_path, decision_path = (
        setup_packet(tmp_path, monkeypatch)
    )
    write_decision(
        decision_path,
        packet=packet,
        decision="HOLD",
        classification="",
        evidence_summary="",
        signal_strength="",
        supports_validation=None,
    )
    result = service.resolve(
        packet_file=packet_path,
        decision_file=decision_path,
        output_path=Path(
            "reports/research/evidence_review_resolutions/"
            "WF-1.json"
        ),
    )
    assert result.held == 1


def test_approval_requires_classification_and_summary(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service, packet, packet_path, decision_path = (
        setup_packet(tmp_path, monkeypatch)
    )
    write_decision(
        decision_path,
        packet=packet,
        evidence_summary="",
        classification="",
    )
    with pytest.raises(RoutedEvidenceReviewError):
        service.resolve(
            packet_file=packet_path,
            decision_file=decision_path,
            output_path=Path(
                "reports/research/evidence_review_resolutions/"
                "WF-1.json"
            ),
        )


def test_candidate_queue_tamper_blocks_resolution(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service, packet, packet_path, decision_path = (
        setup_packet(tmp_path, monkeypatch)
    )
    write_decision(decision_path, packet=packet)
    candidate_path = (
        tmp_path
        / "data/research/evidence_candidates/WF-1.jsonl"
    )
    candidate_path.write_text(
        candidate_path.read_text() + "\n",
        encoding="utf-8",
    )
    with pytest.raises(
        RoutedEvidenceReviewError,
        match="changed after packet generation",
    ):
        service.resolve(
            packet_file=packet_path,
            decision_file=decision_path,
            output_path=Path(
                "reports/research/evidence_review_resolutions/"
                "WF-1.json"
            ),
        )


def test_packet_cannot_be_resolved_twice(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service, packet, packet_path, decision_path = (
        setup_packet(tmp_path, monkeypatch)
    )
    write_decision(decision_path, packet=packet)
    output = Path(
        "reports/research/evidence_review_resolutions/WF-1.json"
    )
    service.resolve(
        packet_file=packet_path,
        decision_file=decision_path,
        output_path=output,
    )
    with pytest.raises(
        RoutedEvidenceReviewError,
        match="already been resolved",
    ):
        service.resolve(
            packet_file=packet_path,
            decision_file=decision_path,
            output_path=output,
        )
