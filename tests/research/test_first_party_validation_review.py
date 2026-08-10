from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.research.first_party_validation_capture import (
    FirstPartyCaptureService,
)
from src.research.first_party_validation_review import (
    FirstPartyReviewError,
    FirstPartyReviewService,
)
from tests.research.test_first_party_validation_capture import (
    CAMPAIGN,
    setup_project,
    submission,
)


def prepare_packet(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    policy = setup_project(tmp_path, monkeypatch)
    input_path = tmp_path / "input.json"
    input_path.write_text(
        json.dumps(
            {
                "submissions": [
                    submission(),
                    submission(
                        submission_id="ROW-002",
                        participant_token="RESP-002",
                        source_reference="FORMROW-002",
                        evidence_kind="structured_response",
                        attestation_basis="direct_response",
                        action_confirmed=False,
                        evidence_summary=(
                            "The contractor described checking old messages "
                            "manually and often leaving outcomes unclassified."
                        ),
                    ),
                ]
            }
        ),
        encoding="utf-8",
    )
    report = FirstPartyCaptureService().capture(
        input_file=input_path,
        policy_file=policy,
        output_file=Path(
            "reports/research/first_party_capture/capture.json"
        ),
    )
    service = FirstPartyReviewService()
    packet = service.prepare(
        candidate_file=Path(report["candidate_path"]),
        policy_file=policy,
        packet_output=Path(
            "reports/research/first_party_review_packets/packet.json"
        ),
        decision_template_output=Path(
            "reports/research/first_party_review_packets/template.json"
        ),
    )
    return service, packet


def decision_payload(packet, *, approve_hold_only: bool = False) -> dict:
    decisions = []
    for item in packet.items:
        if item.eligibility.value == "blocked":
            continue
        decision = "APPROVE"
        if item.eligibility.value == "hold_only":
            decision = "APPROVE" if approve_hold_only else "HOLD"
        decisions.append(
            {
                "review_id": item.review_id,
                "decision": decision,
                "reason": "Human reviewer checked the bounded record.",
            }
        )
    return {
        "packet_id": packet.packet_id,
        "packet_hash": packet.packet_hash,
        "reviewer_reference": "reviewer-1",
        "decisions": decisions,
    }


def write_decisions(
    tmp_path: Path,
    packet,
    *,
    approve_hold_only: bool = False,
) -> Path:
    path = (
        tmp_path
        / "reports/research/first_party_review_packets/decisions.json"
    )
    path.write_text(
        json.dumps(
            decision_payload(
                packet,
                approve_hold_only=approve_hold_only,
            )
        ),
        encoding="utf-8",
    )
    return path


def test_packet_separates_importable_and_taxonomy_gap(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, packet = prepare_packet(tmp_path, monkeypatch)
    assert packet.eligible_candidates == 1
    assert packet.hold_only_candidates == 1
    assert packet.blocked_candidates == 0
    assert packet.proposed_primary_entries == 1


def test_hold_only_item_cannot_be_approved(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service, packet = prepare_packet(tmp_path, monkeypatch)
    decisions = write_decisions(
        tmp_path,
        packet,
        approve_hold_only=True,
    )
    with pytest.raises(
        FirstPartyReviewError,
        match="hold-only",
    ):
        service.resolve(
            packet_file=Path(
                "reports/research/first_party_review_packets/packet.json"
            ),
            decision_file=decisions,
            output_file=Path(
                "reports/research/first_party_review_resolutions/"
                "resolution.json"
            ),
        )


def test_resolution_promotes_only_approved_eligible_item(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service, packet = prepare_packet(tmp_path, monkeypatch)
    decisions = write_decisions(tmp_path, packet)
    result = service.resolve(
        packet_file=Path(
            "reports/research/first_party_review_packets/packet.json"
        ),
        decision_file=decisions,
        output_file=Path(
            "reports/research/first_party_review_resolutions/"
            "resolution.json"
        ),
    )
    assert result.approved == 1
    assert result.held == 1
    verified = Path(result.verified_intake_path)
    records = [json.loads(line) for line in verified.read_text().splitlines()]
    assert len(records) == 1
    assert records[0]["source_trust"] == (
        "human_attested_first_party"
    )


def test_candidate_change_after_packet_blocks_resolution(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service, packet = prepare_packet(tmp_path, monkeypatch)
    decisions = write_decisions(tmp_path, packet)
    candidate_path = Path(
        f"data/research/first_party_candidates/{CAMPAIGN}.jsonl"
    )
    candidate_path.write_text(
        candidate_path.read_text() + "\n",
        encoding="utf-8",
    )
    with pytest.raises(
        FirstPartyReviewError,
        match="changed after",
    ):
        service.resolve(
            packet_file=Path(
                "reports/research/first_party_review_packets/packet.json"
            ),
            decision_file=decisions,
            output_file=Path(
                "reports/research/first_party_review_resolutions/"
                "resolution.json"
            ),
        )


def test_packet_cannot_be_resolved_twice(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service, packet = prepare_packet(tmp_path, monkeypatch)
    decisions = write_decisions(tmp_path, packet)
    service.resolve(
        packet_file=Path(
            "reports/research/first_party_review_packets/packet.json"
        ),
        decision_file=decisions,
        output_file=Path(
            "reports/research/first_party_review_resolutions/"
            "resolution.json"
        ),
    )
    Path(
        "reports/research/first_party_review_resolutions/resolution.json"
    ).unlink()
    with pytest.raises(
        FirstPartyReviewError,
        match="already been resolved",
    ):
        service.resolve(
            packet_file=Path(
                "reports/research/first_party_review_packets/packet.json"
            ),
            decision_file=decisions,
            output_file=Path(
                "reports/research/first_party_review_resolutions/"
                "resolution.json"
            ),
        )


def test_resolution_can_record_no_approvals(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service, packet = prepare_packet(tmp_path, monkeypatch)
    payload = decision_payload(packet)
    for decision in payload["decisions"]:
        decision["decision"] = "HOLD"
        decision["reason"] = "More first-party confirmation is required."
    decisions = (
        tmp_path
        / "reports/research/first_party_review_packets/decisions.json"
    )
    decisions.write_text(json.dumps(payload), encoding="utf-8")
    result = service.resolve(
        packet_file=Path(
            "reports/research/first_party_review_packets/packet.json"
        ),
        decision_file=decisions,
        output_file=Path(
            "reports/research/first_party_review_resolutions/"
            "resolution.json"
        ),
    )
    assert result.approved == 0
    assert Path(result.verified_intake_path).is_file()
    assert Path(result.verified_intake_path).read_text() == ""
