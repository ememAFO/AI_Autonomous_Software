from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.research.verified_intake_mapping import (
    MappingEligibility,
    VerifiedIntakeMappingError,
    VerifiedIntakeMappingService,
)

WORKFLOW = "WF-1"


def intake_record(
    *,
    source_id: str = "EV-1",
    review_id: str = "ER-1",
    resolution_id: str = "RES-1",
    **overrides,
) -> dict:
    record = {
        "resolution_id": resolution_id,
        "packet_id": "P-1",
        "packet_hash": "hash-p1",
        "workflow_id": WORKFLOW,
        "review_id": review_id,
        "source_id": source_id,
        "reviewer_reference": "reviewer-1",
        "decision": "APPROVE",
        "decision_reason": "Checked.",
        "evidence_summary": "A bounded public finding.",
        "classification": "source-verified",
        "signal_strength": "strong",
        "supports_validation": True,
        "canonical_url": "https://example.com/source",
        "title": "Evidence",
        "adapter_name": "hound",
        "adapter_version": "13.1.0",
        "retrieved_at": "2026-08-05T00:00:00+00:00",
        "content_hash": "abc123",
        "candidate_queue_reference": (
            "data/research/evidence_candidates/WF-1.jsonl"
        ),
        "source_type_hint": "unknown",
        "official_hint": False,
        "published_date_hint": "",
        "verified_at": "2026-08-05T00:01:00+00:00",
    }
    record.update(overrides)
    return record


def setup_inputs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    records: list[dict] | None = None,
    source_mappings: dict | None = None,
):
    monkeypatch.chdir(tmp_path)
    intake = (
        tmp_path
        / "data/research/verified_evidence_intake/WF-1.jsonl"
    )
    resolution = (
        tmp_path
        / "reports/research/evidence_review_resolutions/WF-1.json"
    )
    policy = tmp_path / "config/mapping.json"
    plan = (
        tmp_path
        / "reports/intelligence/validation_plans/"
        "lead_and_follow_up_validation_plan.md"
    )
    for path in (intake, resolution, policy, plan):
        path.parent.mkdir(parents=True, exist_ok=True)
    selected = records or [intake_record()]
    intake.write_text(
        "".join(json.dumps(record) + "\n" for record in selected),
        encoding="utf-8",
    )
    resolution.write_text(
        json.dumps(
            {
                "resolution_id": "RES-1",
                "packet_id": "P-1",
                "packet_hash": "hash-p1",
                "workflow_id": WORKFLOW,
                "approved": len(selected),
                "verified_intake_path": str(intake),
            }
        ),
        encoding="utf-8",
    )
    policy.write_text(
        json.dumps(
            {
                "policy_id": "POL-1",
                "workflow_id": WORKFLOW,
                "theme": "lead + follow up",
                "validation_plan_path": (
                    "reports/intelligence/validation_plans/"
                    "lead_and_follow_up_validation_plan.md"
                ),
                "target_log_path": (
                    "reports/intelligence/validation_evidence_log.json"
                ),
                "source_mappings": source_mappings
                or {
                    "EV-1": {
                        "source_trust": "public_dataset",
                        "evidence_type": "manual_research",
                        "rationale": "Public secondary research.",
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    plan.write_text("# Plan\n", encoding="utf-8")
    return intake, resolution, policy


def prepare(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    **kwargs,
):
    intake, resolution, policy = setup_inputs(
        tmp_path,
        monkeypatch,
        **kwargs,
    )
    return VerifiedIntakeMappingService().prepare(
        intake_file=intake,
        resolution_file=resolution,
        policy_file=policy,
        packet_output=Path(
            "reports/research/verified_intake_mappings/WF-1.json"
        ),
        approval_template_output=Path(
            "reports/research/verified_intake_mappings/"
            "WF-1-approval.json"
        ),
    )


def test_prepare_maps_public_research_as_secondary(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    packet = prepare(tmp_path, monkeypatch)
    assert packet.eligible_records == 1
    assert packet.proposed_primary_entries == 0
    assert packet.proposed_secondary_entries == 1
    item = packet.items[0]
    assert item.eligibility is MappingEligibility.ELIGIBLE
    assert item.source_trust == "public_dataset"
    assert item.evidence_type == "manual_research"
    assert item.first_party_eligible is False


def test_vendor_mapping_is_competitor_secondary(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    packet = prepare(
        tmp_path,
        monkeypatch,
        source_mappings={
            "EV-1": {
                "source_trust": "public_competitor",
                "evidence_type": "competitor_check",
                "rationale": "Vendor feature documentation.",
            }
        },
    )
    assert packet.items[0].gate_role == "secondary"
    assert packet.items[0].source_trust == "public_competitor"


def test_public_mapping_cannot_use_primary_type(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    packet = prepare(
        tmp_path,
        monkeypatch,
        source_mappings={
            "EV-1": {
                "source_trust": "public_dataset",
                "evidence_type": "customer_interview",
                "rationale": "Invalid mapping.",
            }
        },
    )
    assert packet.blocked_records == 1
    assert "source_trust_evidence_type_mismatch" in (
        packet.items[0].blocking_reasons
    )
    assert "public_mapping_cannot_be_primary" in (
        packet.items[0].blocking_reasons
    )


def test_missing_source_mapping_is_blocked(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    packet = prepare(
        tmp_path,
        monkeypatch,
        source_mappings={"OTHER": {}},
    )
    assert packet.blocked_records == 1
    assert "source_mapping_missing" in (
        packet.items[0].blocking_reasons
    )


def test_workflow_mismatch_blocks_preparation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    intake, resolution, policy = setup_inputs(
        tmp_path,
        monkeypatch,
    )
    payload = json.loads(policy.read_text())
    payload["workflow_id"] = "OTHER"
    policy.write_text(json.dumps(payload))
    with pytest.raises(
        VerifiedIntakeMappingError,
        match="workflow_id",
    ):
        VerifiedIntakeMappingService().prepare(
            intake_file=intake,
            resolution_file=resolution,
            policy_file=policy,
            packet_output=Path(
                "reports/research/verified_intake_mappings/a.json"
            ),
            approval_template_output=Path(
                "reports/research/verified_intake_mappings/a-approval.json"
            ),
        )


def test_existing_source_reference_blocks_mapping(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    setup_inputs(tmp_path, monkeypatch)
    log_path = (
        tmp_path
        / "reports/intelligence/validation_evidence_log.json"
    )
    log_path.write_text(
        json.dumps(
            {
                "evidence": [
                    {
                        "theme": "lead + follow up",
                        "validation_plan_path": (
                            "reports/intelligence/validation_plans/"
                            "lead_and_follow_up_validation_plan.md"
                        ),
                        "evidence_type": "manual_research",
                        "evidence_summary": "Existing.",
                        "source_reference": (
                            "stage4e:WF-1:EV-1:ER-1"
                        ),
                        "signal_strength": "strong",
                        "supports_validation": True,
                        "timestamp": "2026-08-05T00:00:00+00:00",
                        "notes": "",
                        "source_trust": "public_dataset",
                    }
                ]
            }
        )
    )
    service = VerifiedIntakeMappingService()
    packet = service.prepare(
        intake_file=Path(
            "data/research/verified_evidence_intake/WF-1.jsonl"
        ),
        resolution_file=Path(
            "reports/research/evidence_review_resolutions/WF-1.json"
        ),
        policy_file=Path("config/mapping.json"),
        packet_output=Path(
            "reports/research/verified_intake_mappings/WF-1.json"
        ),
        approval_template_output=Path(
            "reports/research/verified_intake_mappings/"
            "WF-1-approval.json"
        ),
    )
    assert packet.blocked_records == 1
    assert "source_reference_already_in_validation_log" in (
        packet.items[0].blocking_reasons
    )
