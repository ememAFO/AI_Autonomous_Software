from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.security.live_capture_security import (
    LiveCaptureSecurityError,
    RequestEnvelope,
    SyntheticRateLimiter,
    public_error_from_exception,
    required_response_headers,
    validate_request_envelope,
)

POLICY_PATH = Path("config/eop_0001_stage4j_security_policy_v0.1.json")
GATE_PATH = Path("config/eop_0001_stage4j_security_gate_v0.1.json")


def body(payload: dict) -> bytes:
    return json.dumps(payload).encode()


def envelope(
    payload: dict,
    *,
    kind: str = "research",
    method: str = "POST",
    content_type: str = "application/json",
    origin: str | None = None,
    query_string: str = "",
) -> RequestEnvelope:
    return RequestEnvelope(
        request_kind=kind,
        method=method,
        content_type=content_type,
        body=body(payload),
        origin=origin,
        query_string=query_string,
    )


def test_gate_has_no_network_or_http_adapter() -> None:
    gate = json.loads(GATE_PATH.read_text(encoding="utf-8"))
    assert gate["network_listener_present"] is False
    assert gate["http_adapter_present"] is False
    assert gate["live_security_controls_enabled"] is False
    assert not any(gate["protected_actions"].values())


def test_policy_denies_all_origins_until_explicitly_approved() -> None:
    policy = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
    assert policy["origin"]["mode"] == "deny_all_until_origin_approved"
    assert policy["origin"]["approved_origins"] == []
    assert policy["origin"]["wildcard_origin_allowed"] is False


def test_post_json_is_the_only_transport_contract() -> None:
    policy = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
    assert policy["transport"]["allowed_methods"] == ["POST"]
    assert policy["transport"]["allowed_content_types"] == ["application/json"]
    assert policy["transport"]["query_string_submission_allowed"] is False
    assert policy["transport"]["participant_token_in_url_allowed"] is False


def test_valid_json_envelope_passes_non_live_shape_checks() -> None:
    payload = {"participant_role": "electrical_business_owner"}
    assert (
        validate_request_envelope(
            envelope(payload),
            require_approved_origin=False,
        )
        == payload
    )


@pytest.mark.parametrize("method", ["GET", "PUT", "PATCH", "DELETE"])
def test_other_methods_fail_closed(method: str) -> None:
    with pytest.raises(
        LiveCaptureSecurityError,
        match="request_method_not_allowed",
    ):
        validate_request_envelope(
            envelope({"x": 1}, method=method),
            require_approved_origin=False,
        )


@pytest.mark.parametrize(
    "content_type",
    ["text/plain", "application/x-www-form-urlencoded", "multipart/form-data"],
)
def test_non_json_content_types_fail_closed(content_type: str) -> None:
    with pytest.raises(
        LiveCaptureSecurityError,
        match="content_type_not_allowed",
    ):
        validate_request_envelope(
            envelope({"x": 1}, content_type=content_type),
            require_approved_origin=False,
        )


def test_json_content_type_may_include_utf8_charset() -> None:
    payload = {"x": 1}
    assert (
        validate_request_envelope(
            envelope(payload, content_type="application/json; charset=utf-8"),
            require_approved_origin=False,
        )
        == payload
    )


def test_query_string_submission_is_rejected() -> None:
    with pytest.raises(
        LiveCaptureSecurityError,
        match="query_string_submission_forbidden",
    ):
        validate_request_envelope(
            envelope({"x": 1}, query_string="participant_token=secret"),
            require_approved_origin=False,
        )


def test_research_body_limit_is_enforced() -> None:
    policy = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
    max_bytes = policy["request_limits"]["research_max_body_bytes"]
    request = RequestEnvelope(
        request_kind="research",
        method="POST",
        content_type="application/json",
        body=b"{" + (b"x" * max_bytes) + b"}",
    )
    with pytest.raises(LiveCaptureSecurityError, match="request_body_too_large"):
        validate_request_envelope(request, require_approved_origin=False)


def test_contact_body_limit_is_enforced() -> None:
    policy = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
    max_bytes = policy["request_limits"]["contact_max_body_bytes"]
    request = RequestEnvelope(
        request_kind="contact",
        method="POST",
        content_type="application/json",
        body=b"{" + (b"x" * max_bytes) + b"}",
    )
    with pytest.raises(LiveCaptureSecurityError, match="request_body_too_large"):
        validate_request_envelope(request, require_approved_origin=False)


def test_non_utf8_body_is_rejected() -> None:
    request = RequestEnvelope(
        request_kind="research",
        method="POST",
        content_type="application/json",
        body=b"\xff\xfe",
    )
    with pytest.raises(LiveCaptureSecurityError, match="request_body_not_utf8"):
        validate_request_envelope(request, require_approved_origin=False)


def test_non_object_json_is_rejected() -> None:
    request = RequestEnvelope(
        request_kind="research",
        method="POST",
        content_type="application/json",
        body=b"[]",
    )
    with pytest.raises(LiveCaptureSecurityError, match="request_json_not_object"):
        validate_request_envelope(request, require_approved_origin=False)


def test_json_depth_limit_is_enforced() -> None:
    payload: dict = {"value": "x"}
    for _ in range(9):
        payload = {"nested": payload}
    with pytest.raises(LiveCaptureSecurityError, match="json_depth_exceeded"):
        validate_request_envelope(
            envelope(payload),
            require_approved_origin=False,
        )


def test_array_limit_is_enforced() -> None:
    policy = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
    count = policy["request_limits"]["max_array_items"] + 1
    with pytest.raises(LiveCaptureSecurityError, match="json_array_too_large"):
        validate_request_envelope(
            envelope({"values": ["x"] * count}),
            require_approved_origin=False,
        )


def test_string_limit_is_enforced() -> None:
    policy = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
    count = policy["request_limits"]["max_string_length"] + 1
    with pytest.raises(LiveCaptureSecurityError, match="json_string_too_long"):
        validate_request_envelope(
            envelope({"value": "x" * count}),
            require_approved_origin=False,
        )


def test_origin_is_fail_closed_while_allowlist_is_empty() -> None:
    with pytest.raises(
        LiveCaptureSecurityError,
        match="origin_missing_or_not_approved",
    ):
        validate_request_envelope(
            envelope({"x": 1}, origin="https://example.invalid")
        )


def test_missing_origin_is_fail_closed() -> None:
    with pytest.raises(
        LiveCaptureSecurityError,
        match="origin_missing_or_not_approved",
    ):
        validate_request_envelope(envelope({"x": 1}))


def test_public_error_does_not_expose_internal_reason() -> None:
    exc = LiveCaptureSecurityError(
        "invalid_request",
        "very_sensitive_internal_validation_detail",
    )
    public = public_error_from_exception(exc)
    assert public.code == "invalid_request"
    assert "sensitive" not in public.message
    assert "validation_detail" not in public.message


def test_unknown_exception_becomes_generic_unavailable() -> None:
    public = public_error_from_exception(RuntimeError("database password leaked"))
    assert public.code == "temporarily_unavailable"
    assert "password" not in public.message
    assert "database" not in public.message


def test_required_security_headers_are_declared() -> None:
    headers = required_response_headers()
    required = {
        "Content-Security-Policy",
        "Referrer-Policy",
        "X-Content-Type-Options",
        "Permissions-Policy",
        "Cache-Control",
        "Cross-Origin-Opener-Policy",
        "Cross-Origin-Resource-Policy",
        "Strict-Transport-Security",
    }
    assert required <= set(headers)
    assert headers["Cache-Control"] == "no-store"
    assert headers["X-Content-Type-Options"] == "nosniff"


def test_contact_access_is_human_authorized_only() -> None:
    policy = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
    access = policy["contact_access"]
    assert access["anonymous_contact_read_allowed"] is False
    assert access["browser_contact_read_allowed"] is False
    assert access["participant_contact_automatic"] is False
    assert access["human_authorization_required_for_contact_access"] is True


def test_production_secrets_are_not_repo_or_agent_authorized() -> None:
    policy = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
    secrets = policy["secrets"]
    assert secrets["production_secrets_in_repo_allowed"] is False
    assert secrets["production_secrets_available_to_agents"] is False
    assert secrets["environment_or_managed_secret_store_required"] is True


def test_privacy_and_retention_remain_prerequisites() -> None:
    policy = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
    prerequisites = policy["privacy_and_retention_prerequisites"]
    assert prerequisites["privacy_notice_live_review_required"] is True
    assert prerequisites["production_retention_schedule_required"] is True
    assert prerequisites["deletion_process_required"] is True
    assert prerequisites["data_access_process_required"] is True


class FakeClock:
    def __init__(self) -> None:
        self.value = 1000.0

    def __call__(self) -> float:
        return self.value

    def advance(self, seconds: float) -> None:
        self.value += seconds


def test_synthetic_rate_limiter_blocks_after_research_limit() -> None:
    clock = FakeClock()
    limiter = SyntheticRateLimiter(request_kind="research", clock=clock)
    policy = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
    limit = policy["rate_limit_design"]["research_requests_per_window"]
    for _ in range(limit):
        limiter.check("ephemeral-client-key")
    with pytest.raises(LiveCaptureSecurityError, match="rate_limit_exceeded"):
        limiter.check("ephemeral-client-key")


def test_rate_limit_window_expires() -> None:
    clock = FakeClock()
    limiter = SyntheticRateLimiter(request_kind="contact", clock=clock)
    policy = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
    design = policy["rate_limit_design"]
    for _ in range(design["contact_requests_per_window"]):
        limiter.check("ephemeral-client-key")
    clock.advance(design["window_seconds"] + 1)
    limiter.check("ephemeral-client-key")


def test_rate_limiter_stores_only_hashed_keys() -> None:
    limiter = SyntheticRateLimiter(request_kind="research")
    limiter.check("raw-network-identifier")
    stored = limiter.raw_keys()
    assert "raw-network-identifier" not in stored
    assert len(stored) == 1
    only = next(iter(stored))
    assert len(only) == 64


def test_rate_limit_design_is_not_live_approved() -> None:
    policy = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
    design = policy["rate_limit_design"]
    assert design["status"] == "PROPOSED_NOT_LIVE_APPROVED"
    assert design["raw_network_identifier_persistence_allowed"] is False
    assert design["distributed_backend_required_before_multi_instance_deployment"] is True


def test_replay_and_idempotency_remain_live_prerequisites() -> None:
    policy = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
    replay = policy["replay_and_idempotency"]
    assert replay["status"] == "DESIGN_REQUIRED_BEFORE_LIVE"
    assert replay["idempotency_key_transport_contract_required_before_live"] is True
    assert replay["replay_cache_required_before_live"] is True
