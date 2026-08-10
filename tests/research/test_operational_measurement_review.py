from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.research.operational_measurement_capture import (
    OperationalMeasurementCaptureService,
)
from src.research.operational_measurement_review import (
    OperationalMeasurementReviewError,
    OperationalMeasurementReviewService,
)
from tests.research.test_operational_measurement_capture import (
    PROGRAM,
    measurement,
    setup_project,
    write_input,
)


def prepare_packet(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    policy = setup_project(tmp_path, monkeypatch)
    input_path = write_input(
        tmp_path,
        {"measurements": [measurement()]},
    )
    report = OperationalMeasurementCaptureService().capture(
        input_file=input_path,
        policy_file=policy,
        output_file=Path(
            "reports/research/operational_measurement_capture/"
            "capture.json"
        ),
    )
    service = OperationalMeasurementReviewService()
    packet = service.prepare(
        candidate_file=Path(report["candidate_path"]),
        policy_file=policy,
        packet_output=Path(
            "reports/research/"
            "operational_measurement_review_packets/packet.json"
        ),
        decision_template_output=Path(
            "reports/research/"
            "operational_measurement_review_packets/template.json"
        ),
    )
    return service, packet


def write_decisions(
    tmp_path: Path,
    packet,
    *,
    decision: str = "APPROVE",
) -> Path:
    path = (
        tmp_path
        / "reports/research/"
        "operational_measurement_review_packets/decisions.json"
    )
    path.write_text(
        json.dumps(
            {
                "packet_id": packet.packet_id,
                "packet_hash": packet.packet_hash,
                "reviewer_reference": "EMEM-OM-REVIEW-001",
                "decisions": [
                    {
                        "review_id": item.review_id,
                        "decision": decision,
                        "reason": (
                            "The measurement is bounded, traceable, and "
                            "appropriately described as observational."
                        ),
                    }
                    for item in packet.items
                    if item.eligibility.value == "eligible"
                ],
            }
        ),
        encoding="utf-8",
    )
    return path


def test_prepare_packet_keeps_measurements_out_of_evidence_log(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, packet = prepare_packet(tmp_path, monkeypatch)
    assert packet.total_measurements == 1
    assert packet.eligible_measurements == 1
    assert packet.blocked_measurements == 0
    assert packet.validation_log_import_allowed is False
    assert packet.taxonomy_status == (
        "separate_operational_measurement"
    )
    template = json.loads(
        Path(
            "reports/research/"
            "operational_measurement_review_packets/template.json"
        ).read_text(encoding="utf-8")
    )
    assert template["validation_log_import_allowed"] is False


def test_resolve_approve_writes_verified_measurement(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service, packet = prepare_packet(tmp_path, monkeypatch)
    decisions = write_decisions(tmp_path, packet)
    resolution = service.resolve(
        packet_file=Path(
            "reports/research/"
            "operational_measurement_review_packets/packet.json"
        ),
        decision_file=decisions,
        output_file=Path(
            "reports/research/"
            "operational_measurement_review_resolutions/"
            "resolution.json"
        ),
    )
    assert resolution.approved == 1
    assert resolution.validation_log_import_allowed is False
    verified = Path(
        resolution.verified_measurement_path
    ).read_text(encoding="utf-8")
    record = json.loads(verified.strip())
    assert record["measurement_program_id"] == PROGRAM
    assert record["review_decision"] == "APPROVE"
    assert record["validation_log_import_allowed"] is False


def test_resolve_hold_writes_no_verified_records(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service, packet = prepare_packet(tmp_path, monkeypatch)
    decisions = write_decisions(
        tmp_path,
        packet,
        decision="HOLD",
    )
    resolution = service.resolve(
        packet_file=Path(
            "reports/research/"
            "operational_measurement_review_packets/packet.json"
        ),
        decision_file=decisions,
        output_file=Path(
            "reports/research/"
            "operational_measurement_review_resolutions/"
            "resolution.json"
        ),
    )
    assert resolution.approved == 0
    assert resolution.held == 1
    assert Path(
        resolution.verified_measurement_path
    ).read_text(encoding="utf-8") == ""


def test_resolution_requires_every_decision(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service, packet = prepare_packet(tmp_path, monkeypatch)
    path = (
        tmp_path
        / "reports/research/"
        "operational_measurement_review_packets/decisions.json"
    )
    path.write_text(
        json.dumps(
            {
                "packet_id": packet.packet_id,
                "packet_hash": packet.packet_hash,
                "reviewer_reference": "EMEM-OM-REVIEW-001",
                "decisions": [],
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(
        OperationalMeasurementReviewError,
        match="requires a decision",
    ):
        service.resolve(
            packet_file=Path(
                "reports/research/"
                "operational_measurement_review_packets/"
                "packet.json"
            ),
            decision_file=path,
            output_file=Path(
                "reports/research/"
                "operational_measurement_review_resolutions/"
                "resolution.json"
            ),
        )


def test_resolution_rejects_second_resolution(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service, packet = prepare_packet(tmp_path, monkeypatch)
    decisions = write_decisions(tmp_path, packet)
    service.resolve(
        packet_file=Path(
            "reports/research/"
            "operational_measurement_review_packets/packet.json"
        ),
        decision_file=decisions,
        output_file=Path(
            "reports/research/"
            "operational_measurement_review_resolutions/one.json"
        ),
    )
    with pytest.raises(
        OperationalMeasurementReviewError,
        match="already been resolved",
    ):
        service.resolve(
            packet_file=Path(
                "reports/research/"
                "operational_measurement_review_packets/"
                "packet.json"
            ),
            decision_file=decisions,
            output_file=Path(
                "reports/research/"
                "operational_measurement_review_resolutions/"
                "two.json"
            ),
        )


def test_resolution_rejects_tampered_candidate_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service, packet = prepare_packet(tmp_path, monkeypatch)
    decisions = write_decisions(tmp_path, packet)
    candidate = Path(packet.candidate_path)
    candidate.write_text(
        candidate.read_text(encoding="utf-8") + "\n",
        encoding="utf-8",
    )
    with pytest.raises(
        OperationalMeasurementReviewError,
        match="changed after packet creation",
    ):
        service.resolve(
            packet_file=Path(
                "reports/research/"
                "operational_measurement_review_packets/"
                "packet.json"
            ),
            decision_file=decisions,
            output_file=Path(
                "reports/research/"
                "operational_measurement_review_resolutions/"
                "resolution.json"
            ),
        )
