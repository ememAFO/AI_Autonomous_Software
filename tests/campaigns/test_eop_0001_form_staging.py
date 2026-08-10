from __future__ import annotations

import importlib.util
import json
from pathlib import Path

ROOT = Path.cwd()
VALIDATOR_PATH = ROOT / "scripts/validate_eop_0001_form_staging.py"
SPEC = importlib.util.spec_from_file_location(
    "validate_eop_0001_form_staging",
    VALIDATOR_PATH,
)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("Could not load Stage 4I validator")
VALIDATOR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VALIDATOR)
APP_ROOT = VALIDATOR.APP_ROOT
GATE_PATH = VALIDATOR.GATE_PATH
REQUIRED_FILES = VALIDATOR.REQUIRED_FILES
validate = VALIDATOR.validate


def load(relative: Path) -> dict:
    return json.loads((ROOT / relative).read_text(encoding="utf-8"))


def read(relative: Path) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_required_files_exist() -> None:
    assert all((ROOT / path).is_file() for path in REQUIRED_FILES)


def test_static_validator_passes() -> None:
    assert validate(ROOT) == []


def test_staging_gate_is_closed() -> None:
    gate = load(GATE_PATH)
    assert gate["status"] == "NOT_APPROVED_FOR_PUBLIC_DEPLOYMENT"
    assert gate["allowed_host"] == "127.0.0.1"
    assert all(
        value is False
        for value in gate["protected_actions"].values()
    )


def test_network_submission_is_disabled() -> None:
    gate = load(GATE_PATH)
    assert gate["network_submission_enabled"] is False
    assert gate["server_side_storage_enabled"] is False


def test_research_form_has_no_direct_contact_inputs() -> None:
    html = read(APP_ROOT / "index.html").lower()
    assert 'id="name"' not in html
    assert 'id="email"' not in html
    assert 'id="phone"' not in html
    assert 'id="address"' not in html
    assert 'id="postcode"' not in html


def test_contact_form_is_a_separate_document() -> None:
    research = read(APP_ROOT / "index.html")
    contact = read(APP_ROOT / "contact.html")
    assert "contact-name" not in research
    assert "contact-name" in contact
    assert "contact-value" in contact


def test_forms_have_no_action_attribute() -> None:
    research = read(APP_ROOT / "index.html")
    contact = read(APP_ROOT / "contact.html")
    assert "<form id=" in research
    assert "<form id=" in contact
    assert "<form action=" not in research
    assert "<form action=" not in contact


def test_content_security_policy_blocks_connections() -> None:
    assert "connect-src 'none'" in read(APP_ROOT / "index.html")
    assert "connect-src 'none'" in read(APP_ROOT / "contact.html")


def test_javascript_contains_no_network_api() -> None:
    scripts = (
        read(APP_ROOT / "assets/research-form.js")
        + read(APP_ROOT / "assets/contact-form.js")
    )
    assert "fetch(" not in scripts
    assert "XMLHttpRequest" not in scripts
    assert "WebSocket" not in scripts
    assert "sendBeacon" not in scripts


def test_javascript_contains_no_persistent_browser_storage() -> None:
    scripts = (
        read(APP_ROOT / "assets/research-form.js")
        + read(APP_ROOT / "assets/contact-form.js")
    )
    assert "localStorage" not in scripts
    assert "sessionStorage" not in scripts
    assert "document.cookie" not in scripts


def test_research_staging_payload_is_synthetic() -> None:
    script = read(APP_ROOT / "assets/research-form.js")
    assert "staging_only: true" in script
    assert "live_evidence_eligible: false" in script
    assert "synthetic_submission: true" in script
    assert "supports_validation: false" in script


def test_contact_payload_is_excluded_from_stage4g() -> None:
    script = read(APP_ROOT / "assets/contact-form.js")
    assert "stage4g_research_capture_allowed: false" in script


def test_public_form_remains_hold_only() -> None:
    mapping = load(APP_ROOT / "field_mapping.json")
    assert mapping["public_form_treatment"] == "hold_only"


def test_research_and_contact_use_only_token_linkage() -> None:
    mapping = load(APP_ROOT / "field_mapping.json")
    separation = mapping["research_contact_separation"]
    assert separation["link_field"] == "participant_token"
    assert separation["contact_payload_stage4g_allowed"] is False
    assert (
        separation["direct_identifiers_in_research_payload_allowed"]
        is False
    )


def test_preview_server_refuses_non_loopback_host() -> None:
    script = read(Path("scripts/preview_eop_0001_form_staging.py"))
    assert 'args.host != "127.0.0.1"' in script
    assert "Refusing to bind" in script


def test_preview_server_rejects_write_methods() -> None:
    script = read(Path("scripts/preview_eop_0001_form_staging.py"))
    assert "def do_POST" in script
    assert "def do_PUT" in script
    assert "def do_PATCH" in script
    assert "def do_DELETE" in script
    assert "405" in script


def test_contact_token_uses_url_fragment_not_query_string() -> None:
    research_script = read(APP_ROOT / "assets/research-form.js")
    contact_script = read(APP_ROOT / "assets/contact-form.js")
    assert "contact.html#participant_token=" in research_script
    assert "window.location.hash" in contact_script
    assert "window.history.replaceState" in contact_script


def test_staging_payload_cannot_be_mistaken_for_live_evidence() -> None:
    mapping = load(APP_ROOT / "field_mapping.json")
    staging = mapping["staging_payload"]
    assert staging["staging_only"] is True
    assert staging["live_evidence_eligible"] is False
    assert staging["synthetic_submission"] is True
    assert staging["supports_validation"] is False
