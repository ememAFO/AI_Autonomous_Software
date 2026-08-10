from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.hermes.validation_evidence_log import ValidationEvidenceLog
from src.research.verified_intake_mapping import (
    VerifiedIntakeMappingError,
    VerifiedIntakeMappingService,
)
from tests.research.test_verified_intake_mapping import (
    prepare,
)


def approval_payload(packet, *, decision: str = "APPROVE") -> dict:
    return {
        "packet_id": packet.packet_id,
        "packet_hash": packet.packet_hash,
        "approval_reference": "human-mapper-1",
        "decisions": [
            {
                "mapping_id": item.mapping_id,
                "decision": decision,
                "reason": "Mapping checked.",
            }
            for item in packet.items
            if item.eligibility.value == "eligible"
        ],
    }


def write_approval(
    tmp_path: Path,
    packet,
    *,
    decision: str = "APPROVE",
) -> Path:
    path = (
        tmp_path
        / "reports/research/verified_intake_mappings/"
        "WF-1-approved.json"
    )
    path.write_text(
        json.dumps(approval_payload(packet, decision=decision)),
        encoding="utf-8",
    )
    return path


def apply(
    tmp_path: Path,
    service: VerifiedIntakeMappingService,
    packet,
    approval: Path,
):
    return service.apply(
        packet_file=Path(
            "reports/research/verified_intake_mappings/WF-1.json"
        ),
        approval_file=approval,
        output_file=Path(
            "reports/research/validation_evidence_imports/WF-1.json"
        ),
        apply_changes=True,
    )


def test_apply_imports_public_secondary_evidence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    packet = prepare(tmp_path, monkeypatch)
    approval = write_approval(tmp_path, packet)
    service = VerifiedIntakeMappingService()
    result = apply(tmp_path, service, packet, approval)

    assert result.imported == 1
    assert result.after_summary["gate_safe_primary_entries"] == 0
    entries = ValidationEvidenceLog().list_entries()
    assert entries[0].source_trust == "public_dataset"
    assert entries[0].evidence_type == "manual_research"
    assert "first_party_eligible=false" in entries[0].notes


def test_apply_requires_explicit_flag(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    packet = prepare(tmp_path, monkeypatch)
    approval = write_approval(tmp_path, packet)
    with pytest.raises(
        VerifiedIntakeMappingError,
        match="explicit",
    ):
        VerifiedIntakeMappingService().apply(
            packet_file=Path(
                "reports/research/verified_intake_mappings/WF-1.json"
            ),
            approval_file=approval,
            output_file=Path(
                "reports/research/validation_evidence_imports/WF-1.json"
            ),
            apply_changes=False,
        )


def test_hold_does_not_modify_validation_log(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    packet = prepare(tmp_path, monkeypatch)
    approval = write_approval(
        tmp_path,
        packet,
        decision="HOLD",
    )
    result = apply(
        tmp_path,
        VerifiedIntakeMappingService(),
        packet,
        approval,
    )
    assert result.imported == 0
    assert result.held == 1
    assert ValidationEvidenceLog().list_entries() == []


def test_incomplete_approval_is_blocked(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    packet = prepare(tmp_path, monkeypatch)
    approval = (
        tmp_path
        / "reports/research/verified_intake_mappings/"
        "WF-1-approved.json"
    )
    approval.write_text(
        json.dumps(
            {
                "packet_id": packet.packet_id,
                "packet_hash": packet.packet_hash,
                "approval_reference": "human-1",
                "decisions": [],
            }
        )
    )
    with pytest.raises(
        VerifiedIntakeMappingError,
        match="requires a decision",
    ):
        apply(
            tmp_path,
            VerifiedIntakeMappingService(),
            packet,
            approval,
        )


def test_packet_cannot_be_imported_twice(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    packet = prepare(tmp_path, monkeypatch)
    approval = write_approval(tmp_path, packet)
    service = VerifiedIntakeMappingService()
    apply(tmp_path, service, packet, approval)
    with pytest.raises(
        VerifiedIntakeMappingError,
        match="already been imported",
    ):
        apply(tmp_path, service, packet, approval)


def test_intake_tamper_blocks_apply(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    packet = prepare(tmp_path, monkeypatch)
    approval = write_approval(tmp_path, packet)
    intake = (
        tmp_path
        / "data/research/verified_evidence_intake/WF-1.jsonl"
    )
    intake.write_text(
        intake.read_text(encoding="utf-8") + "\n",
        encoding="utf-8",
    )
    with pytest.raises(
        VerifiedIntakeMappingError,
        match="changed after",
    ):
        apply(
            tmp_path,
            VerifiedIntakeMappingService(),
            packet,
            approval,
        )
