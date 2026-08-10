from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

import pytest

from src.research.live_capture_storage import (
    LiveCaptureBatchRegistry,
    LiveCaptureStorageService,
    LiveContactOptInStore,
    LiveResearchResponseStore,
)
from src.security.inprocess_capture_http_adapter import (
    InProcessCaptureHttpAdapter,
    InProcessHttpRequest,
)

POLICY_PATH = Path("config/eop_0001_stage4j_http_adapter_policy_v0.1.json")
GATE_PATH = Path("config/eop_0001_stage4j_http_adapter_gate_v0.1.json")


class FakeClock:
    def __init__(self) -> None:
        self.value = 1000.0

    def __call__(self) -> float:
        return self.value

    def advance(self, seconds: float) -> None:
        self.value += seconds


@pytest.fixture
def adapter(tmp_path: Path) -> InProcessCaptureHttpAdapter:
    tag = f"_pytest_http_{tmp_path.name}"
    research = LiveResearchResponseStore(
        LiveResearchResponseStore.DEFAULT_ROOT / tag
    )
    contact = LiveContactOptInStore(
        LiveContactOptInStore.DEFAULT_ROOT / tag
    )
    registry = LiveCaptureBatchRegistry(
        LiveCaptureBatchRegistry.DEFAULT_ROOT / tag
    )
    service = LiveCaptureStorageService(
        research_store=research,
        contact_store=contact,
        batch_registry=registry,
    )
    clock = FakeClock()
    result = InProcessCaptureHttpAdapter(
        storage_service=service,
        clock=clock,
    )
    result._test_clock = clock  # type: ignore[attr-defined]
    yield result
    for root in (research.root, contact.root, registry.root):
        shutil.rmtree(root, ignore_errors=True)


def contract() -> dict[str, Any]:
    return json.loads(
        Path("config/eop_0001_stage4j_capture_contract_v0.1.json").read_text(
            encoding="utf-8"
        )
    )


def valid_research_payload() -> dict[str, Any]:
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


def request(
    path: str,
    payload: dict[str, Any],
    *,
    idempotency_key: str = "idem-stage4jd-001",
    rate_key: str = "rate-stage4jd-client",
    method: str = "POST",
    content_type: str = "application/json",
    query_string: str = "",
) -> InProcessHttpRequest:
    return InProcessHttpRequest(
        path=path,
        method=method,
        content_type=content_type,
        body=json.dumps(payload).encode(),
        idempotency_key=idempotency_key,
        opaque_rate_key=rate_key,
        origin=None,
        query_string=query_string,
    )


def test_gate_remains_network_off() -> None:
    gate = json.loads(GATE_PATH.read_text(encoding="utf-8"))
    assert gate["in_process_adapter_present"] is True
    assert gate["web_framework_present"] is False
    assert gate["network_listener_present"] is False
    assert gate["socket_binding_present"] is False
    assert gate["live_http_adapter_enabled"] is False
    assert not any(gate["protected_actions"].values())


def test_policy_forbids_network_binding_and_live_adapter() -> None:
    policy = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
    assert policy["network_listener_allowed"] is False
    assert policy["socket_binding_allowed"] is False
    assert policy["web_framework_dependency_allowed"] is False
    assert policy["live_http_adapter_approved"] is False


def test_research_route_returns_token_but_not_url(
    adapter: InProcessCaptureHttpAdapter,
) -> None:
    response = adapter.handle(request("/research", valid_research_payload()))
    assert response.status == 201
    assert response.body["status"] == "accepted"
    assert response.body["participant_token"].startswith("FPVPT-")
    assert "http" not in response.body["participant_token"].lower()
    assert response.body["live_evidence_eligible"] is False
    assert response.body["stage4g_handoff_allowed"] is False


def test_research_is_stored_in_research_store_only(
    adapter: InProcessCaptureHttpAdapter,
) -> None:
    response = adapter.handle(request("/research", valid_research_payload()))
    assert response.status == 201
    service = adapter.storage_service
    research = service.research_store.read(
        service.research_store.path_for("EOP-0001-FPV-20260805")
    )
    contact = service.contact_store.read(
        service.contact_store.path_for("EOP-0001-FPV-20260805")
    )
    assert len(research) == 1
    assert contact == []


def test_contact_route_requires_research_token(
    adapter: InProcessCaptureHttpAdapter,
) -> None:
    contact_payload = {
        "participant_token": "FPVPT-unknown123",
        "contact_name": "",
        "contact_method": "email",
        "contact_value": "preview@example.invalid",
        "requested_action": "interview",
        "consent_to_contact": True,
    }
    response = adapter.handle(
        request(
            "/contact",
            contact_payload,
            idempotency_key="idem-stage4jd-contact-unknown",
        )
    )
    assert response.status == 400
    assert response.body["code"] == "invalid_request"
    assert "unknown" not in response.body["message"].lower()


def test_contact_response_does_not_echo_contact_data(
    adapter: InProcessCaptureHttpAdapter,
) -> None:
    research = adapter.handle(request("/research", valid_research_payload()))
    token = research.body["participant_token"]
    contact_payload = {
        "participant_token": token,
        "contact_name": "Preview User",
        "contact_method": "email",
        "contact_value": "preview@example.invalid",
        "requested_action": "interview",
        "consent_to_contact": True,
    }
    response = adapter.handle(
        request(
            "/contact",
            contact_payload,
            idempotency_key="idem-stage4jd-contact-001",
            rate_key="rate-stage4jd-contact",
        )
    )
    assert response.status == 201
    rendered = json.dumps(response.body, sort_keys=True)
    assert "preview@example.invalid" not in rendered
    assert "Preview User" not in rendered
    assert response.body["participant_contact_allowed"] is False
    assert response.body["stage4g_handoff_allowed"] is False


def test_idempotent_replay_returns_200_without_second_write(
    adapter: InProcessCaptureHttpAdapter,
) -> None:
    req = request("/research", valid_research_payload())
    first = adapter.handle(req)
    second = adapter.handle(req)
    assert first.status == 201
    assert second.status == 200
    assert second.body["idempotent_replay"] is True
    records = adapter.storage_service.research_store.read(
        adapter.storage_service.research_store.path_for(
            "EOP-0001-FPV-20260805"
        )
    )
    assert len(records) == 1


def test_same_idempotency_key_different_body_conflicts(
    adapter: InProcessCaptureHttpAdapter,
) -> None:
    first = request("/research", valid_research_payload())
    changed_payload = valid_research_payload()
    changed_payload["bounded_comment"] = "A different valid synthetic answer"
    second = request("/research", changed_payload)
    assert adapter.handle(first).status == 201
    response = adapter.handle(second)
    assert response.status == 409
    assert response.body["code"] == "invalid_request"


def test_raw_idempotency_key_is_not_stored(
    adapter: InProcessCaptureHttpAdapter,
) -> None:
    raw = "idem-stage4jd-secretish-key"
    response = adapter.handle(
        request(
            "/research",
            valid_research_payload(),
            idempotency_key=raw,
        )
    )
    assert response.status == 201
    stored = adapter.stored_idempotency_keys()
    assert raw not in stored
    assert len(stored) == 1
    assert len(next(iter(stored))) == 64


def test_idempotency_entry_expires(
    adapter: InProcessCaptureHttpAdapter,
) -> None:
    req = request("/research", valid_research_payload())
    assert adapter.handle(req).status == 201
    clock = adapter._test_clock  # type: ignore[attr-defined]
    ttl = json.loads(POLICY_PATH.read_text(encoding="utf-8"))["idempotency"][
        "ttl_seconds"
    ]
    clock.advance(ttl + 1)
    # The duplicate server identifiers are randomly regenerated, so a new
    # synthetic request is allowed after the in-memory idempotency window.
    response = adapter.handle(req)
    assert response.status == 201


def test_rate_limit_is_integrated(
    adapter: InProcessCaptureHttpAdapter,
) -> None:
    security_policy = json.loads(
        Path("config/eop_0001_stage4j_security_policy_v0.1.json").read_text(
            encoding="utf-8"
        )
    )
    limit = security_policy["rate_limit_design"]["research_requests_per_window"]
    for index in range(limit):
        response = adapter.handle(
            request(
                "/research",
                valid_research_payload(),
                idempotency_key=f"idem-rate-{index:03d}",
                rate_key="same-rate-client",
            )
        )
        assert response.status == 201
    blocked = adapter.handle(
        request(
            "/research",
            valid_research_payload(),
            idempotency_key="idem-rate-blocked",
            rate_key="same-rate-client",
        )
    )
    assert blocked.status == 429
    assert blocked.body["code"] == "rate_limited"


@pytest.mark.parametrize(
    ("method", "expected"),
    [
        ("GET", 405),
        ("PUT", 405),
    ],
)
def test_method_errors_are_mapped(
    adapter: InProcessCaptureHttpAdapter,
    method: str,
    expected: int,
) -> None:
    response = adapter.handle(
        request(
            "/research",
            valid_research_payload(),
            method=method,
        )
    )
    assert response.status == expected
    assert "traceback" not in json.dumps(response.body).lower()


def test_content_type_error_maps_to_415(
    adapter: InProcessCaptureHttpAdapter,
) -> None:
    response = adapter.handle(
        request(
            "/research",
            valid_research_payload(),
            content_type="text/plain",
        )
    )
    assert response.status == 415
    assert response.body["code"] == "unsupported_media_type"


def test_query_string_is_rejected(
    adapter: InProcessCaptureHttpAdapter,
) -> None:
    response = adapter.handle(
        request(
            "/research",
            valid_research_payload(),
            query_string="participant_token=must-not-be-here",
        )
    )
    assert response.status == 400
    assert response.body["code"] == "invalid_request"


def test_unknown_route_is_generic_400(
    adapter: InProcessCaptureHttpAdapter,
) -> None:
    response = adapter.handle(
        request("/unknown", valid_research_payload())
    )
    assert response.status == 400
    assert response.body["code"] == "invalid_request"


def test_security_headers_are_on_success_and_error(
    adapter: InProcessCaptureHttpAdapter,
) -> None:
    success = adapter.handle(request("/research", valid_research_payload()))
    error = adapter.handle(
        request(
            "/research",
            valid_research_payload(),
            method="GET",
            idempotency_key="idem-header-error",
        )
    )
    for response in (success, error):
        assert response.headers["Cache-Control"] == "no-store"
        assert response.headers["X-Content-Type-Options"] == "nosniff"
        assert "Content-Security-Policy" in response.headers
        assert response.headers["Content-Type"] == "application/json"


def test_response_does_not_expose_internal_exception_text(
    adapter: InProcessCaptureHttpAdapter,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def explode(*args: Any, **kwargs: Any) -> Any:
        raise RuntimeError("DATABASE_PASSWORD=super-secret")

    monkeypatch.setattr(
        adapter.storage_service,
        "store_research_request",
        explode,
    )
    response = adapter.handle(request("/research", valid_research_payload()))
    rendered = json.dumps(response.body)
    assert response.status == 503
    assert "DATABASE_PASSWORD" not in rendered
    assert "super-secret" not in rendered



def test_idempotent_replay_cannot_bypass_query_string_security(
    adapter: InProcessCaptureHttpAdapter,
) -> None:
    req = request("/research", valid_research_payload())
    assert adapter.handle(req).status == 201

    replay_with_forbidden_query = InProcessHttpRequest(
        path=req.path,
        method=req.method,
        content_type=req.content_type,
        body=req.body,
        idempotency_key=req.idempotency_key,
        opaque_rate_key=req.opaque_rate_key,
        origin=req.origin,
        query_string="participant_token=must-not-bypass-security",
    )
    response = adapter.handle(replay_with_forbidden_query)
    assert response.status == 400
    assert response.body["code"] == "invalid_request"


def test_idempotent_replay_cannot_bypass_content_type_security(
    adapter: InProcessCaptureHttpAdapter,
) -> None:
    req = request("/research", valid_research_payload())
    assert adapter.handle(req).status == 201

    replay_with_bad_media_type = InProcessHttpRequest(
        path=req.path,
        method=req.method,
        content_type="text/plain",
        body=req.body,
        idempotency_key=req.idempotency_key,
        opaque_rate_key=req.opaque_rate_key,
        origin=req.origin,
        query_string=req.query_string,
    )
    response = adapter.handle(replay_with_bad_media_type)
    assert response.status == 415
    assert response.body["code"] == "unsupported_media_type"


def test_idempotent_replays_are_still_rate_limited(
    adapter: InProcessCaptureHttpAdapter,
) -> None:
    req = request(
        "/research",
        valid_research_payload(),
        rate_key="same-replay-rate-client",
    )
    assert adapter.handle(req).status == 201

    security_policy = json.loads(
        Path("config/eop_0001_stage4j_security_policy_v0.1.json").read_text(
            encoding="utf-8"
        )
    )
    limit = security_policy["rate_limit_design"]["research_requests_per_window"]

    for _ in range(limit - 1):
        replay = adapter.handle(req)
        assert replay.status == 200
        assert replay.body["idempotent_replay"] is True

    blocked = adapter.handle(req)
    assert blocked.status == 429
    assert blocked.body["code"] == "rate_limited"


def test_invalid_research_contract_maps_to_generic_400(
    adapter: InProcessCaptureHttpAdapter,
) -> None:
    payload = valid_research_payload()
    payload["participant_role"] = "invented_client_role"
    response = adapter.handle(
        request(
            "/research",
            payload,
            idempotency_key="idem-invalid-contract-001",
        )
    )
    assert response.status == 400
    assert response.body == {
        "code": "invalid_request",
        "message": "The request could not be accepted.",
    }


def test_invalid_contact_contract_maps_to_generic_400(
    adapter: InProcessCaptureHttpAdapter,
) -> None:
    research = adapter.handle(request("/research", valid_research_payload()))
    token = research.body["participant_token"]

    payload = {
        "participant_token": token,
        "contact_name": "",
        "contact_method": "email",
        "contact_value": "not-an-email",
        "requested_action": "interview",
        "consent_to_contact": True,
    }
    response = adapter.handle(
        request(
            "/contact",
            payload,
            idempotency_key="idem-invalid-contact-001",
            rate_key="rate-invalid-contact",
        )
    )
    assert response.status == 400
    assert response.body == {
        "code": "invalid_request",
        "message": "The request could not be accepted.",
    }


def test_adapter_policy_requires_distributed_backends_before_live() -> None:
    policy = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
    assert policy["idempotency"]["distributed_backend_required_before_live"] is True
    assert policy["rate_limit"]["distributed_backend_required_before_live"] is True
    assert policy["storage"]["live_storage_allowed"] is False
    assert policy["storage"]["stage4g_automatic_handoff_allowed"] is False
