#!/usr/bin/env python3
"""Validate the static EOP-0001 Stage 4H campaign package."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

CAMPAIGN_ROOT = Path("campaigns/eop_0001_live_validation")
GATE_PATH = Path("config/eop_0001_live_campaign_launch_gate.json")

REQUIRED_FILES = (
    CAMPAIGN_ROOT / "README.md",
    CAMPAIGN_ROOT / "campaign_plan.md",
    CAMPAIGN_ROOT / "public_posts.md",
    CAMPAIGN_ROOT / "public_form_spec.md",
    CAMPAIGN_ROOT / "interview_guide.md",
    CAMPAIGN_ROOT / "pilot_offer.md",
    CAMPAIGN_ROOT / "baseline_measurement_plan.md",
    CAMPAIGN_ROOT / "consent_notice.md",
    CAMPAIGN_ROOT / "operator_runbook.md",
    CAMPAIGN_ROOT / "human_review_checklist.md",
    CAMPAIGN_ROOT / "launch_approval_template.json",
    CAMPAIGN_ROOT / "schemas/public_form_response.schema.json",
    CAMPAIGN_ROOT / "schemas/contact_opt_in.schema.json",
    CAMPAIGN_ROOT / "schemas/interview_capture.schema.json",
    CAMPAIGN_ROOT / "schemas/concrete_action_capture.schema.json",
    GATE_PATH,
)

DIRECT_IDENTIFIER_FIELDS = {
    "name",
    "full_name",
    "first_name",
    "last_name",
    "email",
    "email_address",
    "phone",
    "phone_number",
    "mobile",
    "address",
    "street_address",
    "postcode",
    "postal_code",
    "ip_address",
}

def load_object(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError(f"{path} must contain a JSON object")
    return payload

def validate(repo: Path) -> list[str]:
    errors: list[str] = []

    for relative in REQUIRED_FILES:
        path = repo / relative
        if not path.is_file():
            errors.append(f"missing:{relative}")

    if errors:
        return errors

    gate = load_object(repo / GATE_PATH)
    protected = gate.get("protected_actions")
    if not isinstance(protected, dict):
        errors.append("gate:protected_actions_missing")
    elif any(value is not False for value in protected.values()):
        errors.append("gate:protected_action_enabled")

    if gate.get("status") != "NOT_APPROVED_FOR_LAUNCH":
        errors.append("gate:status_must_be_not_approved")

    limits = gate.get("limits")
    if not isinstance(limits, dict):
        errors.append("gate:limits_missing")
    else:
        for key in (
            "maximum_public_posts",
            "maximum_responses",
            "maximum_interviews",
            "maximum_pilot_participants",
        ):
            if limits.get(key) != 0:
                errors.append(f"gate:{key}_must_start_at_zero")

    public_schema = load_object(
        repo / CAMPAIGN_ROOT / "schemas/public_form_response.schema.json"
    )
    public_fields = set(public_schema.get("properties", {}))
    forbidden = sorted(public_fields & DIRECT_IDENTIFIER_FIELDS)
    if forbidden:
        errors.append("public_schema:direct_identifiers:" + ",".join(forbidden))

    contact_schema = load_object(
        repo / CAMPAIGN_ROOT / "schemas/contact_opt_in.schema.json"
    )
    description = str(contact_schema.get("description", "")).lower()
    if "must never be submitted to stage 4g" not in description:
        errors.append("contact_schema:stage4g_separation_warning_missing")

    interview_schema = load_object(
        repo / CAMPAIGN_ROOT / "schemas/interview_capture.schema.json"
    )
    interview_properties = interview_schema.get("properties", {})
    if (
        interview_properties.get("capture_method", {}).get("const")
        != "direct_interview"
    ):
        errors.append("interview_schema:capture_method_invalid")
    if (
        interview_properties.get("evidence_kind", {}).get("const")
        != "customer_interview"
    ):
        errors.append("interview_schema:evidence_kind_invalid")

    action_schema = load_object(
        repo / CAMPAIGN_ROOT / "schemas/concrete_action_capture.schema.json"
    )
    action_properties = action_schema.get("properties", {})
    if action_properties.get("action_confirmed", {}).get("const") is not True:
        errors.append("action_schema:confirmed_action_required")

    public_form = (
        repo / CAMPAIGN_ROOT / "public_form_spec.md"
    ).read_text(encoding="utf-8").lower()
    normalized_public_form = " ".join(public_form.split())
    if (
        "research form and contact form must be separate"
        not in normalized_public_form
    ):
        errors.append("public_form:contact_separation_missing")
    if (
        "does not depend on google forms" not in normalized_public_form
        and "must not depend on google forms"
        not in normalized_public_form
    ):
        errors.append("public_form:provider_neutral_requirement_missing")

    measurement = (
        repo / CAMPAIGN_ROOT / "baseline_measurement_plan.md"
    ).read_text(encoding="utf-8")
    for marker in (
        "taxonomy_status: separate_operational_measurement",
        "validation_log_import_allowed: false",
        "claim_boundary: observational_not_causal",
    ):
        if marker not in measurement:
            errors.append(f"measurement:missing_boundary:{marker}")

    return errors

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", default=".")
    args = parser.parse_args()
    repo = Path(args.repo).resolve()
    errors = validate(repo)
    if errors:
        print("Stage 4H campaign package validation failed:")
        for error in errors:
            print(f"- {error}")
        return 1
    print("Stage 4H campaign package validation passed.")
    print("Launch status: NOT_APPROVED_FOR_LAUNCH")
    print("Protected actions enabled: 0")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
