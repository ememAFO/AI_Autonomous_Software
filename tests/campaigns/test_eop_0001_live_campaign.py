from __future__ import annotations

import importlib.util
import json
from pathlib import Path

ROOT = Path.cwd()
VALIDATOR_PATH = ROOT / "scripts/validate_eop_0001_live_campaign.py"
SPEC = importlib.util.spec_from_file_location(
    "validate_eop_0001_live_campaign",
    VALIDATOR_PATH,
)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("Could not load Stage 4H validator")
VALIDATOR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VALIDATOR)

CAMPAIGN_ROOT = VALIDATOR.CAMPAIGN_ROOT
GATE_PATH = VALIDATOR.GATE_PATH
REQUIRED_FILES = VALIDATOR.REQUIRED_FILES
validate = VALIDATOR.validate


def load(relative: Path) -> dict:
    return json.loads((ROOT / relative).read_text(encoding="utf-8"))


def test_required_campaign_files_exist() -> None:
    assert all((ROOT / path).is_file() for path in REQUIRED_FILES)


def test_static_validator_passes() -> None:
    assert validate(ROOT) == []


def test_launch_gate_starts_closed() -> None:
    gate = load(GATE_PATH)
    assert gate["status"] == "NOT_APPROVED_FOR_LAUNCH"
    assert all(
        value is False
        for value in gate["protected_actions"].values()
    )


def test_launch_limits_start_at_zero() -> None:
    gate = load(GATE_PATH)
    assert gate["limits"]["approved_channels"] == []
    assert gate["limits"]["maximum_public_posts"] == 0
    assert gate["limits"]["maximum_responses"] == 0
    assert gate["limits"]["maximum_interviews"] == 0
    assert gate["limits"]["maximum_pilot_participants"] == 0


def test_public_response_schema_excludes_contact_fields() -> None:
    schema = load(
        CAMPAIGN_ROOT
        / "schemas/public_form_response.schema.json"
    )
    properties = set(schema["properties"])
    assert "name" not in properties
    assert "email" not in properties
    assert "phone" not in properties
    assert "postcode" not in properties
    assert "address" not in properties


def test_contact_schema_is_separate_from_stage4g() -> None:
    schema = load(
        CAMPAIGN_ROOT
        / "schemas/contact_opt_in.schema.json"
    )
    assert (
        "must never be submitted to Stage 4G"
        in schema["description"]
    )


def test_public_form_is_hold_only_by_design() -> None:
    readme = (
        ROOT / CAMPAIGN_ROOT / "README.md"
    ).read_text(encoding="utf-8")
    assert "Public structured response" in readme
    assert "Hold-only" in readme


def test_direct_interview_schema_is_bounded() -> None:
    schema = load(
        CAMPAIGN_ROOT
        / "schemas/interview_capture.schema.json"
    )
    properties = schema["properties"]
    assert properties["capture_method"]["const"] == "direct_interview"
    assert properties["evidence_kind"]["const"] == "customer_interview"
    assert properties["attestation_basis"]["const"] == "interviewer_attested"


def test_concrete_action_requires_confirmation() -> None:
    schema = load(
        CAMPAIGN_ROOT
        / "schemas/concrete_action_capture.schema.json"
    )
    assert schema["properties"]["action_confirmed"]["const"] is True


def test_measurement_lane_cannot_enter_validation_log() -> None:
    plan = (
        ROOT / CAMPAIGN_ROOT / "baseline_measurement_plan.md"
    ).read_text(encoding="utf-8")
    assert "validation_log_import_allowed: false" in plan
    assert "claim_boundary: observational_not_causal" in plan


def test_no_automatic_public_or_outreach_action() -> None:
    gate = load(GATE_PATH)
    protected = gate["protected_actions"]
    assert protected["public_posting_allowed"] is False
    assert protected["automatic_outreach_allowed"] is False
    assert protected["participant_contact_allowed"] is False


def test_negative_evidence_is_required() -> None:
    plan = (
        ROOT / CAMPAIGN_ROOT / "campaign_plan.md"
    ).read_text(encoding="utf-8")
    assert "Counter-hypotheses" in plan
    assert "negative evidence" in plan.lower()
