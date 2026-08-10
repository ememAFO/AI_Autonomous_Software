"""Stage 4J-D in-process HTTP adapter model for EOP-0001.

This module models future HTTP routing/status/header behaviour without binding a
socket or importing a web framework. It is synthetic-test-only.
"""

from __future__ import annotations

import hashlib
import json
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.research.live_capture_contract import LiveCaptureContractError
from src.research.live_capture_storage import (
    LiveCaptureStorageError,
    LiveCaptureStorageService,
)
from src.security.live_capture_security import (
    LiveCaptureSecurityError,
    RequestEnvelope,
    SyntheticRateLimiter,
    public_error_from_exception,
    required_response_headers,
    validate_request_envelope,
)

ADAPTER_POLICY_PATH = Path(
    "config/eop_0001_stage4j_http_adapter_policy_v0.1.json"
)

Clock = Callable[[], float]


class InProcessAdapterError(ValueError):
    """Raised when the Stage 4J-D adapter policy is invalid."""


@dataclass(frozen=True)
class InProcessHttpRequest:
    path: str
    method: str
    content_type: str
    body: bytes
    idempotency_key: str
    opaque_rate_key: str
    origin: str | None = None
    query_string: str = ""


@dataclass(frozen=True)
class InProcessHttpResponse:
    status: int
    headers: dict[str, str]
    body: dict[str, Any]


@dataclass
class _IdempotencyEntry:
    body_hash: str
    response: InProcessHttpResponse
    created_at: float


def _load_policy(path: Path = ADAPTER_POLICY_PATH) -> dict[str, Any]:
    resolved = path.resolve()
    expected_root = (Path.cwd().resolve() / "config").resolve()
    try:
        resolved.relative_to(expected_root)
    except ValueError as exc:
        raise InProcessAdapterError("Adapter policy must remain inside config") from exc
    if not resolved.is_file():
        raise InProcessAdapterError(f"Adapter policy missing: {path}")
    payload = json.loads(resolved.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise InProcessAdapterError("Adapter policy must be a JSON object")
    if payload.get("mode") != "in_process_synthetic_only":
        raise InProcessAdapterError("Adapter mode must remain synthetic-only")
    if payload.get("network_listener_allowed") is not False:
        raise InProcessAdapterError("Network listener must remain forbidden")
    if payload.get("socket_binding_allowed") is not False:
        raise InProcessAdapterError("Socket binding must remain forbidden")
    if payload.get("live_http_adapter_approved") is not False:
        raise InProcessAdapterError("Live HTTP adapter must remain unapproved")
    if any(payload.get("protected_actions", {}).values()):
        raise InProcessAdapterError("Protected actions must remain false")
    return payload


def _body_hash(body: bytes) -> str:
    return hashlib.sha256(body).hexdigest()


def _status_for_security_code(code: str) -> int:
    return {
        "invalid_request": 400,
        "origin_not_allowed": 403,
        "method_not_allowed": 405,
        "request_too_large": 413,
        "unsupported_media_type": 415,
        "rate_limited": 429,
        "temporarily_unavailable": 503,
    }.get(code, 503)


class InProcessCaptureHttpAdapter:
    """Network-free adapter integrating Stage 4J-C → 4J-A → 4J-B."""

    def __init__(
        self,
        *,
        storage_service: LiveCaptureStorageService,
        clock: Clock = time.monotonic,
        policy_path: Path = ADAPTER_POLICY_PATH,
    ) -> None:
        self.policy = _load_policy(policy_path)
        self.storage_service = storage_service
        self.clock = clock
        self.research_limiter = SyntheticRateLimiter(
            request_kind="research",
            clock=clock,
        )
        self.contact_limiter = SyntheticRateLimiter(
            request_kind="contact",
            clock=clock,
        )
        self._idempotency: dict[tuple[str, str], _IdempotencyEntry] = {}

    def _headers(self) -> dict[str, str]:
        headers = required_response_headers()
        headers["Content-Type"] = "application/json"
        return headers

    def _response(self, status: int, body: dict[str, Any]) -> InProcessHttpResponse:
        return InProcessHttpResponse(
            status=status,
            headers=self._headers(),
            body=body,
        )

    def _purge_idempotency(self) -> None:
        ttl = int(self.policy["idempotency"]["ttl_seconds"])
        cutoff = self.clock() - ttl
        self._idempotency = {
            key: entry
            for key, entry in self._idempotency.items()
            if entry.created_at > cutoff
        }

    def _validate_idempotency_key(self, key: str) -> None:
        rules = self.policy["idempotency"]
        if not isinstance(key, str):
            raise LiveCaptureSecurityError(
                "invalid_request",
                "idempotency_key_not_string",
            )
        value = key.strip()
        if len(value) < int(rules["key_min_length"]):
            raise LiveCaptureSecurityError(
                "invalid_request",
                "idempotency_key_too_short",
            )
        if len(value) > int(rules["key_max_length"]):
            raise LiveCaptureSecurityError(
                "invalid_request",
                "idempotency_key_too_long",
            )

    def _route(self, path: str) -> dict[str, Any]:
        route = self.policy["routes"].get(path)
        if not isinstance(route, dict):
            raise LiveCaptureSecurityError(
                "invalid_request",
                "route_not_found",
            )
        return route

    def handle(self, request: InProcessHttpRequest) -> InProcessHttpResponse:
        """Handle one synthetic request without any network activity."""

        try:
            route = self._route(request.path)
            if request.method.strip().upper() != route["method"]:
                raise LiveCaptureSecurityError(
                    "method_not_allowed",
                    "route_method_not_allowed",
                )

            self._validate_idempotency_key(request.idempotency_key)

            kind = str(route["request_kind"])
            envelope = RequestEnvelope(
                request_kind=kind,
                method=request.method,
                content_type=request.content_type,
                body=request.body,
                origin=request.origin,
                query_string=request.query_string,
            )
            payload = validate_request_envelope(
                envelope,
                require_approved_origin=False,
            )

            limiter = (
                self.research_limiter
                if kind == "research"
                else self.contact_limiter
            )
            limiter.check(request.opaque_rate_key)

            # Security-envelope checks and abuse controls deliberately run
            # before idempotency replay. A cached response must never bypass
            # transport validation, forbidden query strings, or rate limits.
            self._purge_idempotency()
            cache_key = (
                request.path,
                hashlib.sha256(
                    request.idempotency_key.strip().encode()
                ).hexdigest(),
            )
            request_hash = _body_hash(request.body)
            existing = self._idempotency.get(cache_key)
            if existing is not None:
                if existing.body_hash != request_hash:
                    return self._response(
                        409,
                        {
                            "code": "invalid_request",
                            "message": "The request could not be accepted.",
                        },
                    )
                cached_body = dict(existing.response.body)
                cached_body["idempotent_replay"] = True
                return InProcessHttpResponse(
                    status=200,
                    headers=dict(existing.response.headers),
                    body=cached_body,
                )

            if kind == "research":
                receipt = self.storage_service.store_research_request(payload)
                records = self.storage_service.research_store.read(
                    self.storage_service.research_store.path_for(
                        receipt.campaign_id
                    )
                )
                matching = [
                    record
                    for record in records
                    if record.get("capture_id") == receipt.capture_id
                ]
                if len(matching) != 1:
                    raise LiveCaptureStorageError(
                        "research_receipt_record_not_unique"
                    )
                response_body = {
                    "status": "accepted",
                    "capture_id": receipt.capture_id,
                    "participant_token": matching[0]["participant_token"],
                    "live_evidence_eligible": False,
                    "stage4g_handoff_allowed": False,
                }
            else:
                receipt = self.storage_service.store_contact_request(payload)
                response_body = {
                    "status": "accepted",
                    "capture_id": receipt.capture_id,
                    "contact_recorded": True,
                    "participant_contact_allowed": False,
                    "stage4g_handoff_allowed": False,
                }

            response = self._response(
                int(route["success_status"]),
                response_body,
            )
            self._idempotency[cache_key] = _IdempotencyEntry(
                body_hash=request_hash,
                response=response,
                created_at=self.clock(),
            )
            return response

        except LiveCaptureSecurityError as exc:
            public = public_error_from_exception(exc)
            return self._response(
                _status_for_security_code(public.code),
                {"code": public.code, "message": public.message},
            )
        except (LiveCaptureContractError, LiveCaptureStorageError):
            return self._response(
                400,
                {
                    "code": "invalid_request",
                    "message": "The request could not be accepted.",
                },
            )
        except Exception:  # noqa: BLE001 - public adapter must fail closed generically
            return self._response(
                503,
                {
                    "code": "temporarily_unavailable",
                    "message": "The service is temporarily unavailable.",
                },
            )

    def stored_idempotency_keys(self) -> set[str]:
        """Return stored cache keys for tests; values are hashed only."""
        return {key_hash for _, key_hash in self._idempotency}


__all__ = [
    "InProcessAdapterError",
    "InProcessCaptureHttpAdapter",
    "InProcessHttpRequest",
    "InProcessHttpResponse",
]
