from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from src.research.first_party_validation_capture import FirstPartyCaptureService
from src.research.live_capture_contract import (
    LiveCaptureContractError,
    normalize_contact_request,
    normalize_research_request,
)

CONTRACT_PATH = Path("config/eop_0001_stage4j_capture_contract_v0.1.json")
POLICY_PATH = Path("config/eop_0001_first_party_validation_policy_v0.2.json")


def contract() -> dict:
    return json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))


def valid_research_request() -> dict:
    values = contract()["allowed_values"]
    return {
        "participant_role": "electrical_business_owner",
        "uk_region": values["uk_region"][0],
        "business_size": values["business_size"][0],
        "monthly_quotes": values["monthly_quotes"][0],
        "recorded_outcomes": values["recorded_outcomes"][:1],
        "unclassified_share": values["unclassified_share"][0],
        "follow_up_methods": values["follow_up_methods"][:1],
        "barriers": values["barriers"][:1],
        "decision_inputs": values["decision_inputs"][:1],
        "most_valuable_outcome": values["most_valuable_outcome"][0],
        "next_action_interest": values["next_action_interest"][0],
        "bounded_comment": "",
        "consent_to_research": True,
    }


def deterministic_token(prefix: str) -> str:
    return {
        "FPVPT": "FPVPT-testparticipant",
        "FPVS": "FPVS-testsubmission",
        "public-form": "public-form-testsource",
    }[prefix]


def test_contract_is_stage4i_v02_hold_only() -> None:
    payload = contract()
    assert payload["question_set_version"] == "EOP-0001-QS-0.2"
    assert payload["consent_version"] == "EOP-0001-CONSENT-0.2"
    assert payload["public_form_treatment"] == "hold_only"
    assert payload["governance_output"]["supports_validation"] is False
    assert payload["governance_output"]["validation_log_import_allowed"] is False


def test_research_request_gets_server_owned_governance() -> None:
    result = normalize_research_request(
        valid_research_request(),
        now=datetime(2026, 8, 10, 12, 0, tzinfo=UTC),
        token_factory=deterministic_token,
    )
    submission = result.stage4g_submission
    assert submission["campaign_id"] == "EOP-0001-FPV-20260805"
    assert submission["submission_id"] == "FPVS-testsubmission"
    assert submission["participant_token"] == "FPVPT-testparticipant"
    assert submission["source_reference"] == "public-form-testsource"
    assert submission["capture_method"] == "public_form"
    assert submission["evidence_kind"] == "structured_response"
    assert submission["attestation_basis"] == "direct_response"
    assert submission["supports_validation"] is False
    assert submission["synthetic_submission"] is False


@pytest.mark.parametrize(
    ("form_role", "stage4g_role"),
    [
        ("electrical_business_owner", "electrician_owner"),
        ("self_employed_electrician", "electrician_owner"),
        ("estimator_or_surveyor", "electrical_contractor_staff"),
        ("quotation_administrator", "electrical_contractor_staff"),
        ("operations_or_contracts_manager", "electrical_contractor_staff"),
        ("other_electrical_trade_role", "electrical_contractor_staff"),
    ],
)
def test_roles_normalize_to_stage4g(form_role: str, stage4g_role: str) -> None:
    request = valid_research_request()
    request["participant_role"] = form_role
    result = normalize_research_request(request, token_factory=deterministic_token)
    assert result.stage4g_submission["participant_role"] == stage4g_role


def test_outside_target_market_fails_closed() -> None:
    request = valid_research_request()
    request["participant_role"] = "not_target_market"
    with pytest.raises(LiveCaptureContractError, match="outside_target_market"):
        normalize_research_request(request)


@pytest.mark.parametrize(
    "field",
    [
        "supports_validation",
        "evidence_kind",
        "signal_strength",
        "campaign_id",
        "synthetic_submission",
        "validation_log_import_allowed",
        "public_deployment_allowed",
    ],
)
def test_client_cannot_claim_governance(field: str) -> None:
    request = valid_research_request()
    request[field] = False
    with pytest.raises(LiveCaptureContractError, match="client_authority_forbidden"):
        normalize_research_request(request)


@pytest.mark.parametrize("field", ["email", "phone", "full_name", "postcode"])
def test_direct_identifiers_are_forbidden_in_research(field: str) -> None:
    request = valid_research_request()
    request[field] = "not allowed"
    with pytest.raises(LiveCaptureContractError, match="client_authority_forbidden"):
        normalize_research_request(request)


def test_research_comment_rejects_email() -> None:
    request = valid_research_request()
    request["bounded_comment"] = "Contact me at person@example.com about this."
    with pytest.raises(LiveCaptureContractError, match="email_detected"):
        normalize_research_request(request)


def test_research_requires_consent() -> None:
    request = valid_research_request()
    request["consent_to_research"] = False
    with pytest.raises(LiveCaptureContractError, match="research_consent_required"):
        normalize_research_request(request)


def test_stage4j_output_is_compatible_with_stage4g_hold_only_policy() -> None:
    result = normalize_research_request(
        valid_research_request(),
        token_factory=deterministic_token,
    )
    policy = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
    service = FirstPartyCaptureService()
    candidate, reasons = service._candidate(
        raw=result.stage4g_submission,
        index=1,
        policy=policy,
        policy_hash="test-policy-hash",
    )
    assert reasons == []
    assert candidate is not None
    assert candidate["review_mode"] == "hold_only"
    assert candidate["evidence_type"] == ""
    assert candidate["supports_validation"] is False


def valid_contact_request() -> dict:
    return {
        "participant_token": "FPVPT-testparticipant",
        "contact_name": "",
        "contact_method": "email",
        "contact_value": "preview@example.invalid",
        "requested_action": "interview",
        "consent_to_contact": True,
    }


def test_contact_name_is_optional_and_contact_stays_outside_stage4g() -> None:
    record = normalize_contact_request(valid_contact_request())
    assert record["contact_name"] == ""
    assert record["stage4g_research_capture_allowed"] is False
    assert record["participant_contact_allowed"] is False


def test_contact_rejects_client_timestamp() -> None:
    request = valid_contact_request()
    request["captured_at"] = "2026-08-10T12:00:00Z"
    with pytest.raises(LiveCaptureContractError, match="client_authority_forbidden"):
        normalize_contact_request(request)


def test_contact_rejects_invalid_email() -> None:
    request = valid_contact_request()
    request["contact_value"] = "not-an-email"
    with pytest.raises(LiveCaptureContractError, match="contact_email_invalid"):
        normalize_contact_request(request)


def test_contact_requires_consent() -> None:
    request = valid_contact_request()
    request["consent_to_contact"] = False
    with pytest.raises(LiveCaptureContractError, match="contact_consent_required"):
        normalize_contact_request(request)
