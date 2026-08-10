from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.research.first_party_validation_capture import (
    FirstPartyCaptureService,
)

CAMPAIGN = "EOP-0001-FPV-20260805"


def policy_payload() -> dict:
    return {
        "policy_id": "POL-1",
        "campaign_id": CAMPAIGN,
        "theme": "lead + follow up",
        "validation_plan_path": (
            "reports/intelligence/validation_plans/"
            "lead_and_follow_up_validation_plan.md"
        ),
        "target_log_path": (
            "reports/intelligence/validation_evidence_log.json"
        ),
        "consent_version": "CONSENT-1",
        "allowed_participant_roles": [
            "electrician_owner",
            "customer_client",
        ],
        "evidence_rules": {
            "structured_response": {
                "evidence_type": "",
                "review_mode": "hold_only",
                "allowed_capture_methods": ["public_form"],
                "allowed_attestation_bases": ["direct_response"],
                "requires_consent": True,
                "requires_participant_token": True,
                "requires_confirmed_action": False,
                "requires_measurement": False,
            },
            "waitlist_signup": {
                "evidence_type": "waitlist_signup",
                "review_mode": "importable",
                "allowed_capture_methods": ["public_form"],
                "allowed_attestation_bases": ["recorded_action"],
                "requires_consent": True,
                "requires_participant_token": True,
                "requires_confirmed_action": True,
                "requires_measurement": False,
            },
            "willingness_to_pay": {
                "evidence_type": "willingness_to_pay",
                "review_mode": "importable",
                "allowed_capture_methods": ["payment_intent"],
                "allowed_attestation_bases": ["recorded_action"],
                "requires_consent": True,
                "requires_participant_token": True,
                "requires_confirmed_action": True,
                "requires_measurement": False,
            },
            "landing_page_result": {
                "evidence_type": "landing_page_result",
                "review_mode": "importable",
                "allowed_capture_methods": [
                    "landing_page_aggregate"
                ],
                "allowed_attestation_bases": [
                    "aggregate_measurement"
                ],
                "requires_consent": False,
                "requires_participant_token": False,
                "requires_confirmed_action": False,
                "requires_measurement": True,
            },
        },
    }


def setup_project(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> Path:
    monkeypatch.chdir(tmp_path)
    policy = tmp_path / "config/policy.json"
    policy.parent.mkdir(parents=True)
    policy.write_text(json.dumps(policy_payload()), encoding="utf-8")
    plan = (
        tmp_path
        / "reports/intelligence/validation_plans/"
        "lead_and_follow_up_validation_plan.md"
    )
    plan.parent.mkdir(parents=True)
    plan.write_text("# Plan\n", encoding="utf-8")
    return policy


def submission(**overrides) -> dict:
    data = {
        "campaign_id": CAMPAIGN,
        "submission_id": "ROW-001",
        "captured_at": "2026-08-05T12:00:00+01:00",
        "capture_method": "public_form",
        "evidence_kind": "waitlist_signup",
        "participant_token": "RESP-001",
        "participant_role": "electrician_owner",
        "attestation_basis": "recorded_action",
        "evidence_summary": (
            "An electrical contractor owner completed the explicit "
            "waitlist action to test a manual quotation tracker."
        ),
        "signal_strength": "medium",
        "supports_validation": True,
        "source_reference": "FORMROW-001",
        "consent_to_research": True,
        "consent_version": "CONSENT-1",
        "question_set_version": "QS-1",
        "action_confirmed": True,
        "self_submission": False,
        "synthetic_submission": False,
    }
    data.update(overrides)
    return data


def run_capture(
    tmp_path: Path,
    policy: Path,
    submissions: list[dict],
    *,
    output_name: str = "capture.json",
):
    input_path = tmp_path / f"input-{output_name}"
    input_path.write_text(
        json.dumps({"submissions": submissions}),
        encoding="utf-8",
    )
    return FirstPartyCaptureService().capture(
        input_file=input_path,
        policy_file=policy,
        output_file=Path(
            f"reports/research/first_party_capture/{output_name}"
        ),
    )


def test_valid_waitlist_action_is_captured(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    policy = setup_project(tmp_path, monkeypatch)
    report = run_capture(tmp_path, policy, [submission()])
    assert report["accepted"] == 1
    assert report["blocked"] == 0
    candidates = Path(report["candidate_path"]).read_text()
    assert '"evidence_type": "waitlist_signup"' in candidates


def test_direct_identifier_field_is_blocked(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    policy = setup_project(tmp_path, monkeypatch)
    report = run_capture(
        tmp_path,
        policy,
        [submission(email="person@example.com")],
    )
    assert report["accepted"] == 0
    assert "forbidden_fields:email" in report[
        "blocked_submissions"
    ][0]["blocking_reasons"]


def test_self_submission_is_blocked(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    policy = setup_project(tmp_path, monkeypatch)
    report = run_capture(
        tmp_path,
        policy,
        [submission(self_submission=True)],
    )
    assert report["accepted"] == 0
    assert "self_submission_not_allowed" in report[
        "blocked_submissions"
    ][0]["blocking_reasons"]


def test_duplicate_response_fingerprint_is_blocked(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    policy = setup_project(tmp_path, monkeypatch)
    first = submission()
    second = submission(
        submission_id="ROW-002",
        source_reference="FORMROW-002",
    )
    report = run_capture(tmp_path, policy, [first, second])
    assert report["accepted"] == 1
    assert report["blocked"] == 1
    assert "duplicate_response_fingerprint" in report[
        "blocked_submissions"
    ][0]["blocking_reasons"]


def test_structured_form_response_is_hold_only_candidate(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    policy = setup_project(tmp_path, monkeypatch)
    record = submission(
        evidence_kind="structured_response",
        attestation_basis="direct_response",
        action_confirmed=False,
        evidence_summary=(
            "The contractor reported tracking unanswered quotations in "
            "messages and could not consistently classify final outcomes."
        ),
    )
    report = run_capture(tmp_path, policy, [record])
    candidate = json.loads(
        Path(report["candidate_path"]).read_text().strip()
    )
    assert candidate["review_mode"] == "hold_only"
    assert candidate["evidence_type"] == ""


def test_price_intent_requires_confirmed_action(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    policy = setup_project(tmp_path, monkeypatch)
    record = submission(
        capture_method="payment_intent",
        evidence_kind="willingness_to_pay",
        action_confirmed=False,
    )
    report = run_capture(tmp_path, policy, [record])
    assert report["accepted"] == 0
    assert "confirmed_action_required" in report[
        "blocked_submissions"
    ][0]["blocking_reasons"]


def test_aggregate_measurement_needs_no_participant_consent(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    policy = setup_project(tmp_path, monkeypatch)
    record = submission(
        capture_method="landing_page_aggregate",
        evidence_kind="landing_page_result",
        participant_token="",
        attestation_basis="aggregate_measurement",
        consent_to_research=False,
        consent_version="",
        action_confirmed=False,
        measurement_count=12,
        measurement_window="2026-08-01/2026-08-05",
        evidence_summary=(
            "The controlled landing page recorded twelve completed "
            "interest actions during the stated measurement window."
        ),
    )
    report = run_capture(tmp_path, policy, [record])
    assert report["accepted"] == 1
    assert report["blocked"] == 0
