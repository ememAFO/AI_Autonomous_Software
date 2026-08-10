"""Stage 4J-A trusted request normalization for EOP-0001.

This module has no network listener and performs no persistence. It converts
untrusted participant request data into factory-owned canonical records and a
Stage 4G-compatible hold-only submission.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from src.research.first_party_validation_capture import EMAIL_PATTERN, PHONE_PATTERN

CONTRACT_PATH = Path("config/eop_0001_stage4j_capture_contract_v0.1.json")
TOKEN_PATTERN = re.compile(r"^[A-Za-z0-9_.:-]{3,120}$")
TokenFactory = Callable[[str], str]


class LiveCaptureContractError(ValueError):
    """Raised when an untrusted request violates the Stage 4J-A contract."""


@dataclass(frozen=True)
class NormalizedResearchRequest:
    research_record: dict[str, Any]
    stage4g_submission: dict[str, Any]


def _default_token_factory(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex}"


def _load_contract(path: Path = CONTRACT_PATH) -> dict[str, Any]:
    resolved = path.resolve()
    expected_root = (Path.cwd().resolve() / "config").resolve()
    try:
        resolved.relative_to(expected_root)
    except ValueError as exc:
        raise LiveCaptureContractError("Contract path must remain inside config") from exc
    if not resolved.is_file():
        raise LiveCaptureContractError(f"Capture contract does not exist: {path}")
    payload = json.loads(resolved.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise LiveCaptureContractError("Capture contract must be a JSON object")
    return payload


def _require_object(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise LiveCaptureContractError("Request must be a JSON object")
    return raw


def _reject_unknown_and_forbidden(
    raw: dict[str, Any],
    *,
    allowed: set[str],
    contract: dict[str, Any],
    research: bool,
) -> None:
    forbidden = set(contract.get("client_forbidden_authority_fields", []))
    if research:
        forbidden |= set(contract.get("direct_identifiers_forbidden_in_research", []))
    for key in raw:
        if key in forbidden:
            raise LiveCaptureContractError(f"client_authority_forbidden:{key}")
        if key not in allowed:
            raise LiveCaptureContractError(f"unexpected_field:{key}")


def _required_text(raw: dict[str, Any], field: str, allowed: set[str]) -> str:
    value = raw.get(field)
    if not isinstance(value, str) or not value.strip():
        raise LiveCaptureContractError(f"{field}_missing_or_invalid")
    value = value.strip()
    if value not in allowed:
        raise LiveCaptureContractError(f"{field}_not_allowed")
    return value


def _allowed_list(
    raw: dict[str, Any],
    field: str,
    allowed: set[str],
    *,
    maximum: int | None = None,
    exclusive: str | None = None,
) -> list[str]:
    value = raw.get(field)
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise LiveCaptureContractError(f"{field}_must_be_string_list")
    if len(value) != len(set(value)):
        raise LiveCaptureContractError(f"{field}_contains_duplicates")
    if any(item not in allowed for item in value):
        raise LiveCaptureContractError(f"{field}_contains_disallowed_value")
    if maximum is not None and len(value) > maximum:
        raise LiveCaptureContractError(f"{field}_too_many_values")
    if exclusive and exclusive in value and len(value) > 1:
        raise LiveCaptureContractError(f"{field}_exclusive_choice_conflict")
    return list(value)


def _iso_now(now: datetime | None) -> str:
    value = now or datetime.now(UTC)
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).isoformat()


def _summary(data: dict[str, Any]) -> str:
    parts = [
        f"role={data['participant_role']}",
        f"uk_region={data['uk_region']}",
        f"business_size={data['business_size']}",
        f"monthly_quotes={data['monthly_quotes']}",
        "recorded_outcomes=" + ("|".join(data["recorded_outcomes"]) or "none_selected"),
        f"unclassified_share={data['unclassified_share']}",
        "follow_up_methods=" + ("|".join(data["follow_up_methods"]) or "none_selected"),
        "barriers=" + ("|".join(data["barriers"]) or "none_selected"),
        "decision_inputs=" + ("|".join(data["decision_inputs"]) or "none_selected"),
        f"most_valuable_outcome={data['most_valuable_outcome']}",
        f"next_action_interest={data['next_action_interest']}",
    ]
    if data["bounded_comment"]:
        parts.append(f"bounded_comment={data['bounded_comment']}")
    return "; ".join(parts)


def normalize_research_request(
    raw_request: Any,
    *,
    now: datetime | None = None,
    token_factory: TokenFactory = _default_token_factory,
    contract_path: Path = CONTRACT_PATH,
) -> NormalizedResearchRequest:
    contract = _load_contract(contract_path)
    raw = _require_object(raw_request)
    participant_fields = set(contract["participant_supplied_research_fields"])
    _reject_unknown_and_forbidden(
        raw,
        allowed=participant_fields,
        contract=contract,
        research=True,
    )

    allowed_values = contract["allowed_values"]
    role = _required_text(raw, "participant_role", set(allowed_values["participant_role"]))
    if role == "not_target_market":
        raise LiveCaptureContractError("participant_outside_target_market")
    normalized_role = contract["role_normalization"].get(role)
    if not normalized_role:
        raise LiveCaptureContractError("participant_role_has_no_normalization")

    data = {
        "participant_role": role,
        "uk_region": _required_text(raw, "uk_region", set(allowed_values["uk_region"])),
        "business_size": _required_text(raw, "business_size", set(allowed_values["business_size"])),
        "monthly_quotes": _required_text(raw, "monthly_quotes", set(allowed_values["monthly_quotes"])),
        "recorded_outcomes": _allowed_list(
            raw, "recorded_outcomes", set(allowed_values["recorded_outcomes"])
        ),
        "unclassified_share": _required_text(
            raw, "unclassified_share", set(allowed_values["unclassified_share"])
        ),
        "follow_up_methods": _allowed_list(
            raw,
            "follow_up_methods",
            set(allowed_values["follow_up_methods"]),
            exclusive=contract["interaction_rules"]["follow_up_methods_exclusive"],
        ),
        "barriers": _allowed_list(
            raw,
            "barriers",
            set(allowed_values["barriers"]),
            maximum=int(contract["interaction_rules"]["barriers_maximum"]),
            exclusive=contract["interaction_rules"]["barriers_exclusive"],
        ),
        "decision_inputs": _allowed_list(
            raw,
            "decision_inputs",
            set(allowed_values["decision_inputs"]),
            maximum=int(contract["interaction_rules"]["decision_inputs_maximum"]),
            exclusive=contract["interaction_rules"]["decision_inputs_exclusive"],
        ),
        "most_valuable_outcome": _required_text(
            raw,
            "most_valuable_outcome",
            set(allowed_values["most_valuable_outcome"]),
        ),
        "next_action_interest": _required_text(
            raw,
            "next_action_interest",
            set(allowed_values["next_action_interest"]),
        ),
        "bounded_comment": "",
    }

    comment = raw.get("bounded_comment", "")
    if not isinstance(comment, str):
        raise LiveCaptureContractError("bounded_comment_must_be_text")
    comment = " ".join(comment.split())
    if len(comment) > int(contract["limits"]["bounded_comment_max_length"]):
        raise LiveCaptureContractError("bounded_comment_too_long")
    if EMAIL_PATTERN.search(comment):
        raise LiveCaptureContractError("email_detected_in_research_comment")
    if PHONE_PATTERN.search(comment):
        raise LiveCaptureContractError("phone_detected_in_research_comment")
    data["bounded_comment"] = comment

    if raw.get("consent_to_research") is not True:
        raise LiveCaptureContractError("research_consent_required")

    token = token_factory("FPVPT")
    submission_id = token_factory("FPVS")
    source_reference = token_factory("public-form")
    for label, value in (
        ("participant_token", token),
        ("submission_id", submission_id),
        ("source_reference", source_reference),
    ):
        if not TOKEN_PATTERN.fullmatch(value):
            raise LiveCaptureContractError(f"server_generated_{label}_invalid")

    captured_at = _iso_now(now)
    evidence_summary = _summary(data)
    if len(evidence_summary) < 30 or len(evidence_summary) > 1_200:
        raise LiveCaptureContractError("server_generated_evidence_summary_invalid")
    if EMAIL_PATTERN.search(evidence_summary) or PHONE_PATTERN.search(evidence_summary):
        raise LiveCaptureContractError("pii_detected_in_server_generated_summary")

    governance = contract["governance_output"]
    research_record = {
        "record_type": "eop_0001_research_response_v0.2",
        "campaign_id": contract["campaign_id"],
        "submission_id": submission_id,
        "participant_token": token,
        "captured_at": captured_at,
        "source_reference": source_reference,
        "question_set_version": contract["question_set_version"],
        "consent_version": contract["consent_version"],
        "public_form_treatment": contract["public_form_treatment"],
        "validation_log_import_allowed": False,
        "structured_response": data,
        "consent_to_research": True,
    }

    stage4g_submission = {
        "campaign_id": contract["campaign_id"],
        "submission_id": submission_id,
        "participant_token": token,
        "participant_role": normalized_role,
        "capture_method": governance["capture_method"],
        "evidence_kind": governance["evidence_kind"],
        "attestation_basis": governance["attestation_basis"],
        "evidence_summary": evidence_summary,
        "source_reference": source_reference,
        "consent_to_research": True,
        "consent_version": contract["consent_version"],
        "question_set_version": contract["question_set_version"],
        "signal_strength": governance["signal_strength"],
        "supports_validation": False,
        "self_submission": False,
        "synthetic_submission": False,
        "captured_at": captured_at,
    }
    return NormalizedResearchRequest(
        research_record=research_record,
        stage4g_submission=stage4g_submission,
    )


def normalize_contact_request(
    raw_request: Any,
    *,
    now: datetime | None = None,
    contract_path: Path = CONTRACT_PATH,
) -> dict[str, Any]:
    contract = _load_contract(contract_path)
    raw = _require_object(raw_request)
    participant_fields = set(contract["participant_supplied_contact_fields"])
    _reject_unknown_and_forbidden(
        raw,
        allowed=participant_fields,
        contract=contract,
        research=False,
    )

    token = raw.get("participant_token")
    if not isinstance(token, str) or not TOKEN_PATTERN.fullmatch(token.strip()):
        raise LiveCaptureContractError("participant_token_invalid")
    token = token.strip()

    allowed_values = contract["allowed_values"]
    method = _required_text(raw, "contact_method", set(allowed_values["contact_method"]))
    requested_action = _required_text(
        raw, "requested_action", set(allowed_values["requested_action"])
    )

    name = raw.get("contact_name", "")
    if not isinstance(name, str):
        raise LiveCaptureContractError("contact_name_must_be_text")
    name = " ".join(name.split())
    if len(name) > int(contract["limits"]["contact_name_max_length"]):
        raise LiveCaptureContractError("contact_name_too_long")

    value = raw.get("contact_value")
    if not isinstance(value, str) or not value.strip():
        raise LiveCaptureContractError("contact_value_missing")
    value = value.strip()
    if len(value) > int(contract["limits"]["contact_value_max_length"]):
        raise LiveCaptureContractError("contact_value_too_long")
    if method == "email" and not EMAIL_PATTERN.fullmatch(value):
        raise LiveCaptureContractError("contact_email_invalid")
    if method == "phone" and not PHONE_PATTERN.fullmatch(value):
        raise LiveCaptureContractError("contact_phone_invalid")

    if raw.get("consent_to_contact") is not True:
        raise LiveCaptureContractError("contact_consent_required")

    return {
        "record_type": "eop_0001_contact_opt_in_v0.2",
        "participant_token": token,
        "contact_name": name,
        "contact_method": method,
        "contact_value": value,
        "requested_action": requested_action,
        "consent_to_contact": True,
        "captured_at": _iso_now(now),
        "stage4g_research_capture_allowed": False,
        "participant_contact_allowed": False,
    }
