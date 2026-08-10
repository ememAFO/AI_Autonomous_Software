"""Stage 4J-C network-off security contract for future live capture.

No server or socket is created here. This module provides deterministic
validation primitives that a later HTTP adapter must call before any request
can reach the Stage 4J-A/4J-B capture path.
"""

from __future__ import annotations

import hashlib
import json
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

SECURITY_POLICY_PATH = Path("config/eop_0001_stage4j_security_policy_v0.1.json")

Clock = Callable[[], float]


class LiveCaptureSecurityError(ValueError):
    """Internal fail-closed security exception."""

    def __init__(self, public_code: str, internal_reason: str) -> None:
        super().__init__(internal_reason)
        self.public_code = public_code
        self.internal_reason = internal_reason


@dataclass(frozen=True)
class RequestEnvelope:
    request_kind: str
    method: str
    content_type: str
    body: bytes
    origin: str | None = None
    query_string: str = ""


@dataclass(frozen=True)
class PublicError:
    code: str
    message: str


def _load_policy(path: Path = SECURITY_POLICY_PATH) -> dict[str, Any]:
    resolved = path.resolve()
    expected_root = (Path.cwd().resolve() / "config").resolve()
    try:
        resolved.relative_to(expected_root)
    except ValueError as exc:
        raise LiveCaptureSecurityError(
            "temporarily_unavailable",
            "security_policy_outside_config",
        ) from exc
    if not resolved.is_file():
        raise LiveCaptureSecurityError(
            "temporarily_unavailable",
            "security_policy_missing",
        )
    payload = json.loads(resolved.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise LiveCaptureSecurityError(
            "temporarily_unavailable",
            "security_policy_not_object",
        )
    if payload.get("mode") != "synthetic_test_only":
        raise LiveCaptureSecurityError(
            "temporarily_unavailable",
            "security_policy_not_synthetic_only",
        )
    if payload.get("live_security_controls_approved") is not False:
        raise LiveCaptureSecurityError(
            "temporarily_unavailable",
            "live_security_controls_unexpectedly_approved",
        )
    if any(payload.get("protected_actions", {}).values()):
        raise LiveCaptureSecurityError(
            "temporarily_unavailable",
            "protected_action_enabled",
        )
    return payload


def _json_depth_and_nodes(value: Any) -> tuple[int, int]:
    if isinstance(value, dict):
        if not value:
            return 1, 1
        child = [_json_depth_and_nodes(item) for item in value.values()]
        return 1 + max(depth for depth, _ in child), 1 + sum(
            nodes for _, nodes in child
        )
    if isinstance(value, list):
        if not value:
            return 1, 1
        child = [_json_depth_and_nodes(item) for item in value]
        return 1 + max(depth for depth, _ in child), 1 + sum(
            nodes for _, nodes in child
        )
    return 1, 1


def _walk_json(
    value: Any,
    *,
    max_array_items: int,
    max_string_length: int,
) -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            if not isinstance(key, str):
                raise LiveCaptureSecurityError(
                    "invalid_request",
                    "json_object_key_not_string",
                )
            if len(key) > max_string_length:
                raise LiveCaptureSecurityError(
                    "invalid_request",
                    "json_key_too_long",
                )
            _walk_json(
                child,
                max_array_items=max_array_items,
                max_string_length=max_string_length,
            )
    elif isinstance(value, list):
        if len(value) > max_array_items:
            raise LiveCaptureSecurityError(
                "invalid_request",
                "json_array_too_large",
            )
        for child in value:
            _walk_json(
                child,
                max_array_items=max_array_items,
                max_string_length=max_string_length,
            )
    elif isinstance(value, str) and len(value) > max_string_length:
        raise LiveCaptureSecurityError(
            "invalid_request",
            "json_string_too_long",
        )


def validate_request_envelope(
    envelope: RequestEnvelope,
    *,
    policy_path: Path = SECURITY_POLICY_PATH,
    require_approved_origin: bool = True,
) -> dict[str, Any]:
    """Validate transport-independent request metadata and JSON shape.

    `require_approved_origin` exists only so the network-off tests can verify
    the remaining envelope rules while the policy's live origin allow-list is
    deliberately empty. A future HTTP adapter must always use the default True.
    """

    policy = _load_policy(policy_path)
    transport = policy["transport"]
    limits = policy["request_limits"]

    method = envelope.method.strip().upper()
    if method not in set(transport["allowed_methods"]):
        raise LiveCaptureSecurityError(
            "method_not_allowed",
            "request_method_not_allowed",
        )

    media_type = envelope.content_type.split(";", 1)[0].strip().lower()
    if media_type not in set(transport["allowed_content_types"]):
        raise LiveCaptureSecurityError(
            "unsupported_media_type",
            "content_type_not_allowed",
        )

    if envelope.query_string and not transport["query_string_submission_allowed"]:
        raise LiveCaptureSecurityError(
            "invalid_request",
            "query_string_submission_forbidden",
        )

    if envelope.request_kind == "research":
        max_body = int(limits["research_max_body_bytes"])
    elif envelope.request_kind == "contact":
        max_body = int(limits["contact_max_body_bytes"])
    else:
        raise LiveCaptureSecurityError(
            "invalid_request",
            "unknown_request_kind",
        )

    if len(envelope.body) > max_body:
        raise LiveCaptureSecurityError(
            "request_too_large",
            "request_body_too_large",
        )

    try:
        decoded = envelope.body.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise LiveCaptureSecurityError(
            "invalid_request",
            "request_body_not_utf8",
        ) from exc

    try:
        payload = json.loads(decoded)
    except json.JSONDecodeError as exc:
        raise LiveCaptureSecurityError(
            "invalid_request",
            "request_body_not_json",
        ) from exc

    if not isinstance(payload, dict):
        raise LiveCaptureSecurityError(
            "invalid_request",
            "request_json_not_object",
        )

    depth, nodes = _json_depth_and_nodes(payload)
    if depth > int(limits["max_json_depth"]):
        raise LiveCaptureSecurityError(
            "invalid_request",
            "json_depth_exceeded",
        )
    if nodes > int(limits["max_total_nodes"]):
        raise LiveCaptureSecurityError(
            "invalid_request",
            "json_node_limit_exceeded",
        )
    _walk_json(
        payload,
        max_array_items=int(limits["max_array_items"]),
        max_string_length=int(limits["max_string_length"]),
    )

    if require_approved_origin:
        origin_policy = policy["origin"]
        approved = set(origin_policy["approved_origins"])
        if not envelope.origin or envelope.origin not in approved:
            raise LiveCaptureSecurityError(
                "origin_not_allowed",
                "origin_missing_or_not_approved",
            )

    return payload


def public_error_from_exception(exc: Exception) -> PublicError:
    """Return a non-sensitive error suitable for a future HTTP response."""

    allowed_messages = {
        "invalid_request": "The request could not be accepted.",
        "request_too_large": "The request is too large.",
        "unsupported_media_type": "The request format is not supported.",
        "method_not_allowed": "The request method is not supported.",
        "origin_not_allowed": "The request origin is not allowed.",
        "rate_limited": "Too many requests. Try again later.",
        "temporarily_unavailable": "The service is temporarily unavailable.",
    }
    code = (
        exc.public_code
        if isinstance(exc, LiveCaptureSecurityError)
        else "temporarily_unavailable"
    )
    if code not in allowed_messages:
        code = "temporarily_unavailable"
    return PublicError(code=code, message=allowed_messages[code])


def required_response_headers(
    *,
    policy_path: Path = SECURITY_POLICY_PATH,
) -> dict[str, str]:
    policy = _load_policy(policy_path)
    headers = policy.get("future_response_headers", {})
    if not isinstance(headers, dict):
        raise LiveCaptureSecurityError(
            "temporarily_unavailable",
            "security_headers_not_object",
        )
    return {str(key): str(value) for key, value in headers.items()}


class SyntheticRateLimiter:
    """In-memory design test only; never a production distributed limiter."""

    def __init__(
        self,
        *,
        request_kind: str,
        clock: Clock = time.monotonic,
        policy_path: Path = SECURITY_POLICY_PATH,
    ) -> None:
        policy = _load_policy(policy_path)
        design = policy["rate_limit_design"]
        if design["status"] != "PROPOSED_NOT_LIVE_APPROVED":
            raise LiveCaptureSecurityError(
                "temporarily_unavailable",
                "rate_limit_design_status_invalid",
            )
        if request_kind == "research":
            limit = int(design["research_requests_per_window"])
        elif request_kind == "contact":
            limit = int(design["contact_requests_per_window"])
        else:
            raise LiveCaptureSecurityError(
                "invalid_request",
                "unknown_rate_limit_kind",
            )
        self.request_kind = request_kind
        self.limit = limit
        self.window_seconds = int(design["window_seconds"])
        self.clock = clock
        self._events: dict[str, list[float]] = {}

    @staticmethod
    def _key(opaque_rate_key: str) -> str:
        if not isinstance(opaque_rate_key, str) or not opaque_rate_key:
            raise LiveCaptureSecurityError(
                "invalid_request",
                "rate_key_missing",
            )
        return hashlib.sha256(opaque_rate_key.encode()).hexdigest()

    def check(self, opaque_rate_key: str) -> None:
        key = self._key(opaque_rate_key)
        now = self.clock()
        cutoff = now - self.window_seconds
        recent = [
            timestamp
            for timestamp in self._events.get(key, [])
            if timestamp > cutoff
        ]
        if len(recent) >= self.limit:
            self._events[key] = recent
            raise LiveCaptureSecurityError(
                "rate_limited",
                "synthetic_rate_limit_exceeded",
            )
        recent.append(now)
        self._events[key] = recent

    def raw_keys(self) -> set[str]:
        """Expose stored keys to tests; values must be hashes, never raw identifiers."""
        return set(self._events)


__all__ = [
    "LiveCaptureSecurityError",
    "PublicError",
    "RequestEnvelope",
    "SyntheticRateLimiter",
    "public_error_from_exception",
    "required_response_headers",
    "validate_request_envelope",
]
