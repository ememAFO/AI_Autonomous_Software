from __future__ import annotations

import importlib.util
import json
import re
from pathlib import Path
from types import ModuleType

ROOT = Path.cwd()
VALIDATOR_PATH = ROOT / "scripts/validate_eop_0001_form_staging.py"


def load_validator() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "validate_eop_0001_form_staging_v02",
        VALIDATOR_PATH,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("Could not load Stage 4I v0.2 validator")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


VALIDATOR = load_validator()
APP_ROOT = VALIDATOR.APP_ROOT
GATE_PATH = VALIDATOR.GATE_PATH
validate = VALIDATOR.validate


def read(relative: Path) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def load(relative: Path) -> dict:
    return json.loads((ROOT / relative).read_text(encoding="utf-8"))


def test_validator_passes() -> None:
    assert validate(ROOT) == []


def test_gate_remains_closed() -> None:
    gate = load(GATE_PATH)
    assert gate["status"] == "NOT_APPROVED_FOR_PUBLIC_DEPLOYMENT"
    assert all(
        value is False
        for value in gate["protected_actions"].values()
    )


def test_four_sections_are_visible() -> None:
    html = read(APP_ROOT / "index.html")
    for marker in (
        "Section 1 of 4",
        "Section 2 of 4",
        "Section 3 of 4",
        "Section 4 of 4",
    ):
        assert marker in html


def test_section_labels_match_review() -> None:
    html = read(APP_ROOT / "index.html")
    for label in (
        "About your business",
        "Current quotation process",
        "What would help",
        "Optional next step",
    ):
        assert label in html


def test_exclusive_choices_are_declared() -> None:
    html = read(APP_ROOT / "index.html")
    assert 'data-group="follow_up_methods"' in html
    assert 'data-exclusive-value="none"' in html
    assert 'data-group="barriers"' in html
    assert 'data-exclusive-value="not_a_problem"' in html


def test_exclusive_handler_exists() -> None:
    script = read(APP_ROOT / "assets/research-form.js")
    assert "function enforceExclusiveChoice" in script
    assert "exclusive.checked = false" in script


def test_token_warning_is_present() -> None:
    html = read(APP_ROOT / "index.html")
    assert "Keep this token private" in html
    assert "Do not post it in public comments" in html


def test_contact_name_is_optional() -> None:
    html = read(APP_ROOT / "contact.html")
    match = re.search(
        r'<input[^>]+id="contact-name"[^>]*>',
        html,
        re.IGNORECASE,
    )
    assert match is not None
    assert "required" not in match.group(0)


def test_contact_copy_has_no_internal_stage_term() -> None:
    html = read(APP_ROOT / "contact.html")
    assert "Contact details are stored separately" in html
    assert "Stage 4G" not in html


def test_contact_return_navigation_exists() -> None:
    html = read(APP_ROOT / "contact.html")
    assert html.count("Return to the research form") >= 2


def test_error_panels_are_focus_targets() -> None:
    assert 'tabindex="-1"' in read(APP_ROOT / "index.html")
    assert 'tabindex="-1"' in read(APP_ROOT / "contact.html")


def test_contact_completion_is_explicit() -> None:
    html = read(APP_ROOT / "contact.html")
    assert "Preview contact record generated" in html
    assert "Nothing was sent or stored online" in html


def test_mobile_layout_rule_exists() -> None:
    css = read(APP_ROOT / "assets/styles.css")
    assert "@media (max-width: 680px)" in css
    assert "grid-template-columns: 1fr" in css


def test_no_network_submission_api() -> None:
    scripts = (
        read(APP_ROOT / "assets/research-form.js")
        + read(APP_ROOT / "assets/contact-form.js")
    )
    for token in ("fetch(", "XMLHttpRequest", "WebSocket", "sendBeacon"):
        assert token not in scripts


def test_no_persistent_browser_storage() -> None:
    scripts = (
        read(APP_ROOT / "assets/research-form.js")
        + read(APP_ROOT / "assets/contact-form.js")
    )
    for token in ("localStorage", "sessionStorage", "document.cookie"):
        assert token not in scripts


def test_preview_payload_remains_non_live() -> None:
    script = read(APP_ROOT / "assets/research-form.js")
    assert "staging_only: true" in script
    assert "live_evidence_eligible: false" in script
    assert "synthetic_submission: true" in script
    assert "supports_validation: false" in script


def test_contact_payload_remains_outside_stage4g() -> None:
    script = read(APP_ROOT / "assets/contact-form.js")
    assert "stage4g_research_capture_allowed: false" in script


def test_versions_incremented() -> None:
    mapping = load(APP_ROOT / "field_mapping.json")
    assert mapping["question_set_version"] == "EOP-0001-QS-0.2"
    assert mapping["consent_version"] == "EOP-0001-CONSENT-0.2"


def test_visual_review_matrix_required() -> None:
    gate = load(GATE_PATH)
    required = set(gate["required_visual_review"])
    assert "research_form_mobile" in required
    assert "research_validation_error_state" in required
    assert "contact_form_mobile" in required
    assert "contact_completion_state" in required
