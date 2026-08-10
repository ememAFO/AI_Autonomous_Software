"""Stage 4J-B governed local storage boundary for EOP-0001.

The adapter is deliberately network-off and synthetic-test-only. Research and
contact records are stored under physically separate controlled roots. Contact
records never enter Stage 4G research capture.

This module is not a production persistence backend.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from src.research.first_party_validation_storage import (
    ControlledJsonlStore,
)
from src.research.live_capture_contract import (
    CONTRACT_PATH,
    NormalizedResearchRequest,
    normalize_contact_request,
    normalize_research_request,
)
from src.utils.audit_logger import AuditEvent, AuditLogger

STORAGE_POLICY_PATH = Path("config/eop_0001_stage4j_storage_policy_v0.1.json")

IdFactory = Callable[[str], str]


class LiveCaptureStorageError(ValueError):
    """Raised when Stage 4J-B storage violates its governed boundary."""


class LiveResearchResponseStore(ControlledJsonlStore):
    """Synthetic research-response store with no direct identifiers."""

    DEFAULT_ROOT = Path("data/research/live_research_responses")

    def __init__(self, root: str | Path = DEFAULT_ROOT) -> None:
        super().__init__(root=root, expected_relative_root=self.DEFAULT_ROOT)


class LiveContactOptInStore(ControlledJsonlStore):
    """Separate synthetic contact store; never a Stage 4G research store."""

    DEFAULT_ROOT = Path("data/research/live_contact_opt_ins")

    def __init__(self, root: str | Path = DEFAULT_ROOT) -> None:
        super().__init__(root=root, expected_relative_root=self.DEFAULT_ROOT)


class LiveCaptureBatchRegistry(ControlledJsonlStore):
    """Identifier-minimised metadata registry for Stage 4J-B writes."""

    DEFAULT_ROOT = Path("data/research/live_capture_batches")

    def __init__(self, root: str | Path = DEFAULT_ROOT) -> None:
        super().__init__(root=root, expected_relative_root=self.DEFAULT_ROOT)
        self.registry_path = self.root / "registry.jsonl"


@dataclass(frozen=True)
class StorageReceipt:
    capture_id: str
    record_type: str
    campaign_id: str
    storage_mode: str
    stage4g_handoff_allowed: bool
    validation_log_import_allowed: bool


def _default_id_factory(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex}"


def _payload_hash(payload: Any) -> str:
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


def _load_storage_policy(path: Path = STORAGE_POLICY_PATH) -> dict[str, Any]:
    resolved = path.resolve()
    expected_root = (Path.cwd().resolve() / "config").resolve()
    try:
        resolved.relative_to(expected_root)
    except ValueError as exc:
        raise LiveCaptureStorageError(
            "Storage policy path must remain inside config"
        ) from exc
    if not resolved.is_file():
        raise LiveCaptureStorageError(f"Storage policy does not exist: {path}")
    payload = json.loads(resolved.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise LiveCaptureStorageError("Storage policy must be a JSON object")
    if payload.get("storage_mode") != "synthetic_test_only":
        raise LiveCaptureStorageError("Only synthetic_test_only storage is permitted")
    if payload.get("live_storage_approved") is not False:
        raise LiveCaptureStorageError("Live storage must remain unapproved")
    if any(payload.get("protected_actions", {}).values()):
        raise LiveCaptureStorageError("Protected storage actions must remain false")
    return payload


def _iso_now(now: datetime | None) -> str:
    value = now or datetime.now(UTC)
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).isoformat()


def _ensure_no_direct_identifiers(record: dict[str, Any], forbidden: set[str]) -> None:
    stack: list[Any] = [record]
    while stack:
        current = stack.pop()
        if isinstance(current, dict):
            for key, value in current.items():
                if key.lower() in forbidden:
                    raise LiveCaptureStorageError(
                        f"direct_identifier_in_research_record:{key}"
                    )
                stack.append(value)
        elif isinstance(current, list):
            stack.extend(current)


class LiveCaptureStorageService:
    """Persist only synthetic Stage 4J-B records under controlled roots."""

    def __init__(
        self,
        *,
        research_store: LiveResearchResponseStore | None = None,
        contact_store: LiveContactOptInStore | None = None,
        batch_registry: LiveCaptureBatchRegistry | None = None,
        audit_logger: AuditLogger | None = None,
        contract_path: Path = CONTRACT_PATH,
        storage_policy_path: Path = STORAGE_POLICY_PATH,
    ) -> None:
        self.project_root = Path.cwd().resolve()
        self.research_store = research_store or LiveResearchResponseStore()
        self.contact_store = contact_store or LiveContactOptInStore()
        self.batch_registry = batch_registry or LiveCaptureBatchRegistry()
        self.audit_logger = audit_logger or AuditLogger(
            "logs/stage4j_b_capture_audit.log"
        )
        self.contract_path = contract_path
        self.storage_policy_path = storage_policy_path
        self.policy = _load_storage_policy(storage_policy_path)
        self._assert_root_separation()

    def _assert_root_separation(self) -> None:
        roots = {
            self.research_store.root,
            self.contact_store.root,
            self.batch_registry.root,
        }
        if len(roots) != 3:
            raise LiveCaptureStorageError("Stage 4J-B controlled roots must differ")

    def _campaign_id(self) -> str:
        campaign_id = str(self.policy.get("campaign_id", "")).strip()
        if not campaign_id:
            raise LiveCaptureStorageError("Storage policy campaign_id is missing")
        return campaign_id

    def _retention_metadata(self) -> dict[str, Any]:
        retention = self.policy.get("retention", {})
        return {
            "retention_policy_id": self.policy["policy_id"],
            "retention_status": retention.get("status"),
            "automated_deletion_enabled": False,
            "deletion_requires_human_review": True,
        }

    def _audit(
        self,
        *,
        action: str,
        capture_id: str,
        record_type: str,
        participant_token: str,
        extra: dict[str, Any] | None = None,
    ) -> None:
        details: dict[str, Any] = {
            "capture_id": capture_id,
            "record_type": record_type,
            "campaign_id": self._campaign_id(),
            "storage_mode": "synthetic_test_only",
            "participant_link_hash": _payload_hash(participant_token)[:24],
            "live_evidence_eligible": False,
            "stage4g_handoff_allowed": False,
            "validation_log_import_allowed": False,
        }
        if extra:
            details.update(extra)
        self.audit_logger.log(
            AuditEvent(action=action, status="success", details=details)
        )

    def _existing_research(self) -> list[dict[str, Any]]:
        return self.research_store.read(
            self.research_store.path_for(self._campaign_id())
        )

    def _assert_unique_research(
        self,
        normalized: NormalizedResearchRequest,
    ) -> None:
        submission = normalized.stage4g_submission
        for existing in self._existing_research():
            if existing.get("submission_id") == submission["submission_id"]:
                raise LiveCaptureStorageError("duplicate_research_submission_id")
            if existing.get("participant_token") == submission["participant_token"]:
                raise LiveCaptureStorageError("duplicate_research_participant_token")
            if existing.get("source_reference") == submission["source_reference"]:
                raise LiveCaptureStorageError("duplicate_research_source_reference")

    def store_research_request(
        self,
        raw_request: Any,
        *,
        now: datetime | None = None,
        token_factory: IdFactory = _default_id_factory,
        capture_id_factory: IdFactory = _default_id_factory,
    ) -> StorageReceipt:
        normalized = normalize_research_request(
            raw_request,
            now=now,
            token_factory=token_factory,
            contract_path=self.contract_path,
        )
        self._assert_unique_research(normalized)

        record = dict(normalized.research_record)
        forbidden = {
            str(value).lower()
            for value in json.loads(
                self.contract_path.read_text(encoding="utf-8")
            ).get("direct_identifiers_forbidden_in_research", [])
        }
        _ensure_no_direct_identifiers(record, forbidden)

        capture_id = capture_id_factory("LCRES")
        record.update(
            {
                "capture_id": capture_id,
                "storage_mode": "synthetic_test_only",
                "storage_boundary_version": "STAGE4J-B-0.1",
                "stored_at": _iso_now(now),
                "live_evidence_eligible": False,
                "stage4g_handoff_allowed": False,
                "validation_log_import_allowed": False,
                **self._retention_metadata(),
            }
        )
        record["record_hash"] = _payload_hash(record)

        research_path = self.research_store.path_for(self._campaign_id())
        registry_path = self.batch_registry.registry_path
        research_snapshot = ControlledJsonlStore.snapshot(research_path)
        registry_snapshot = ControlledJsonlStore.snapshot(registry_path)

        registry_record = {
            "capture_id": capture_id,
            "record_type": "research",
            "campaign_id": self._campaign_id(),
            "record_hash": record["record_hash"],
            "participant_link_hash": _payload_hash(record["participant_token"])[:24],
            "storage_mode": "synthetic_test_only",
            "stored_at": record["stored_at"],
        }

        try:
            self.research_store.append_many(research_path, [record])
            self.batch_registry.append_many(registry_path, [registry_record])
            self._audit(
                action="stage4j_b_research_store",
                capture_id=capture_id,
                record_type="research",
                participant_token=record["participant_token"],
            )
        except Exception:
            ControlledJsonlStore.restore(research_path, research_snapshot)
            ControlledJsonlStore.restore(registry_path, registry_snapshot)
            raise

        return StorageReceipt(
            capture_id=capture_id,
            record_type="research",
            campaign_id=self._campaign_id(),
            storage_mode="synthetic_test_only",
            stage4g_handoff_allowed=False,
            validation_log_import_allowed=False,
        )

    def _find_research_by_token(
        self,
        participant_token: str,
    ) -> dict[str, Any] | None:
        matches = [
            record
            for record in self._existing_research()
            if record.get("participant_token") == participant_token
        ]
        if len(matches) > 1:
            raise LiveCaptureStorageError(
                "participant_token_not_unique_in_research_store"
            )
        return matches[0] if matches else None

    def store_contact_request(
        self,
        raw_request: Any,
        *,
        now: datetime | None = None,
        capture_id_factory: IdFactory = _default_id_factory,
    ) -> StorageReceipt:
        contact = normalize_contact_request(
            raw_request,
            now=now,
            contract_path=self.contract_path,
        )
        participant_token = str(contact["participant_token"])
        research = self._find_research_by_token(participant_token)
        if research is None:
            raise LiveCaptureStorageError("unknown_research_participant_token")

        contact_fingerprint = _payload_hash(
            {
                "participant_token": participant_token,
                "contact_method": contact["contact_method"],
                "contact_value": str(contact["contact_value"]).strip().lower(),
                "requested_action": contact["requested_action"],
            }
        )
        contact_path = self.contact_store.path_for(self._campaign_id())
        existing = self.contact_store.read(contact_path)
        if any(
            record.get("contact_fingerprint") == contact_fingerprint
            for record in existing
        ):
            raise LiveCaptureStorageError("duplicate_contact_opt_in")

        capture_id = capture_id_factory("LCCON")
        record = dict(contact)
        record.update(
            {
                "capture_id": capture_id,
                "campaign_id": self._campaign_id(),
                "research_capture_id": research["capture_id"],
                "contact_fingerprint": contact_fingerprint,
                "storage_mode": "synthetic_test_only",
                "storage_boundary_version": "STAGE4J-B-0.1",
                "stored_at": _iso_now(now),
                "live_evidence_eligible": False,
                "stage4g_research_capture_allowed": False,
                "stage4g_handoff_allowed": False,
                "validation_log_import_allowed": False,
                **self._retention_metadata(),
            }
        )
        record["record_hash"] = _payload_hash(record)

        registry_path = self.batch_registry.registry_path
        contact_snapshot = ControlledJsonlStore.snapshot(contact_path)
        registry_snapshot = ControlledJsonlStore.snapshot(registry_path)
        registry_record = {
            "capture_id": capture_id,
            "record_type": "contact",
            "campaign_id": self._campaign_id(),
            "record_hash": record["record_hash"],
            "participant_link_hash": _payload_hash(participant_token)[:24],
            "storage_mode": "synthetic_test_only",
            "stored_at": record["stored_at"],
        }

        try:
            self.contact_store.append_many(contact_path, [record])
            self.batch_registry.append_many(registry_path, [registry_record])
            self._audit(
                action="stage4j_b_contact_store",
                capture_id=capture_id,
                record_type="contact",
                participant_token=participant_token,
                extra={
                    "contact_method": contact["contact_method"],
                    "requested_action": contact["requested_action"],
                },
            )
        except Exception:
            ControlledJsonlStore.restore(contact_path, contact_snapshot)
            ControlledJsonlStore.restore(registry_path, registry_snapshot)
            raise

        return StorageReceipt(
            capture_id=capture_id,
            record_type="contact",
            campaign_id=self._campaign_id(),
            storage_mode="synthetic_test_only",
            stage4g_handoff_allowed=False,
            validation_log_import_allowed=False,
        )


__all__ = [
    "LiveCaptureBatchRegistry",
    "LiveCaptureStorageError",
    "LiveCaptureStorageService",
    "LiveContactOptInStore",
    "LiveResearchResponseStore",
    "StorageReceipt",
]
