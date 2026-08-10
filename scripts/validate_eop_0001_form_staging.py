#!/usr/bin/env python3
"""Validate Stage 4I v0.2 local-only form staging."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

APP_ROOT = Path("sandbox/eop_0001_form_staging")
GATE_PATH = Path("config/eop_0001_form_staging_gate.json")

# Backward-compatible public interface used by the Stage 4I v0.1 test suite.
# v0.2 additions are included so one validator describes the complete
# installed staging surface.
REQUIRED_FILES = (
    APP_ROOT / "README.md",
    APP_ROOT / "index.html",
    APP_ROOT / "contact.html",
    APP_ROOT / "assets/styles.css",
    APP_ROOT / "assets/research-form.js",
    APP_ROOT / "assets/contact-form.js",
    APP_ROOT / "field_mapping.json",
    APP_ROOT / "visual_review_checklist.md",
    APP_ROOT / "v0_2_review_targets.md",
    GATE_PATH,
    Path("scripts/preview_eop_0001_form_staging.py"),
    Path("scripts/validate_eop_0001_form_staging.py"),
)


def load_object(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError(f"{path} must contain a JSON object")
    return payload


def validate(repo: Path) -> list[str]:
    errors: list[str] = []

    for relative in REQUIRED_FILES:
        if not (repo / relative).is_file():
            errors.append(f"missing:{relative}")
    if errors:
        return errors

    gate = load_object(repo / GATE_PATH)
    if gate.get("status") != "NOT_APPROVED_FOR_PUBLIC_DEPLOYMENT":
        errors.append("gate:status_not_closed")
    if gate.get("allowed_host") != "127.0.0.1":
        errors.append("gate:host_not_loopback")

    protected = gate.get("protected_actions")
    if not isinstance(protected, dict):
        errors.append("gate:protected_actions_missing")
    elif any(value is not False for value in protected.values()):
        errors.append("gate:protected_action_enabled")

    index = (repo / APP_ROOT / "index.html").read_text(encoding="utf-8")
    contact = (repo / APP_ROOT / "contact.html").read_text(encoding="utf-8")
    research_js = (
        repo / APP_ROOT / "assets/research-form.js"
    ).read_text(encoding="utf-8")
    contact_js = (
        repo / APP_ROOT / "assets/contact-form.js"
    ).read_text(encoding="utf-8")
    css = (
        repo / APP_ROOT / "assets/styles.css"
    ).read_text(encoding="utf-8")

    if "Section 1 of 4" not in index or "Section 4 of 4" not in index:
        errors.append("research:section_structure_missing")
    if "Keep this token private" not in index:
        errors.append("research:token_warning_missing")
    if 'data-exclusive-value="not_a_problem"' not in index:
        errors.append("research:barrier_exclusive_rule_missing")
    if "enforceExclusiveChoice" not in research_js:
        errors.append("research:exclusive_handler_missing")

    if re.search(
        r'<input[^>]+id="contact-name"[^>]+required',
        contact,
        re.IGNORECASE,
    ):
        errors.append("contact:name_must_be_optional")
    if "Return to the research form" not in contact:
        errors.append("contact:return_navigation_missing")
    if "Contact details are stored separately" not in contact:
        errors.append("contact:plain_language_separation_missing")
    if "Stage 4G" in contact:
        errors.append("contact:internal_terminology_exposed")

    if 'tabindex="-1"' not in index or 'tabindex="-1"' not in contact:
        errors.append("errors:focus_target_missing")
    if "@media (max-width: 680px)" not in css:
        errors.append("styles:mobile_breakpoint_missing")

    combined = research_js + contact_js
    for token in ("fetch(", "XMLHttpRequest", "WebSocket", "sendBeacon"):
        if token in combined:
            errors.append(f"javascript:network_api:{token}")
    for token in ("localStorage", "sessionStorage", "document.cookie"):
        if token in combined:
            errors.append(f"javascript:persistent_storage:{token}")

    mapping = load_object(repo / APP_ROOT / "field_mapping.json")
    if mapping.get("public_form_treatment") != "hold_only":
        errors.append("mapping:public_form_not_hold_only")

    separation = mapping.get("research_contact_separation", {})
    if separation.get("contact_name_required") is not False:
        errors.append("mapping:contact_name_not_optional")
    if separation.get("contact_payload_stage4g_allowed") is not False:
        errors.append("mapping:contact_stage4g_not_false")
    if (
        separation.get(
            "direct_identifiers_in_research_payload_allowed"
        )
        is not False
    ):
        errors.append("mapping:research_identifiers_not_false")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", default=".")
    args = parser.parse_args()

    errors = validate(Path(args.repo).resolve())
    if errors:
        print("Stage 4I v0.2 form staging validation failed:")
        for error in errors:
            print(f"- {error}")
        return 1

    print("Stage 4I v0.2.1 form staging validation passed.")
    print("Status: NOT_APPROVED_FOR_PUBLIC_DEPLOYMENT")
    print("Network submission enabled: false")
    print("Server-side storage enabled: false")
    print("Protected actions enabled: 0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
