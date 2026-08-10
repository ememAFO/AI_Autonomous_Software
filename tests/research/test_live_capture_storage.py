from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

import pytest

from src.research.first_party_validation_storage import (
    FirstPartyValidationStorageError,
)
from src.research.live_capture_storage import (
    LiveCaptureBatchRegistry,
    LiveCaptureStorageError,
    LiveCaptureStorageService,
    LiveContactOptInStore,
    LiveResearchResponseStore,
)
from src.utils.audit_logger import AuditEvent

SOURCE_ROOT = Path.cwd().resolve()
CONTRACT_PATH = SOURCE_ROOT / "config/eop_0001_stage4j_capture_contract_v0.1.json"
STORAGE_POLICY_PATH = (
    SOURCE_ROOT / "config/eop_0001_stage4j_storage_policy_v0.1.json"
)
GATE_PATH = SOURCE_ROOT / "config/eop_0001_stage4j_storage_gate_v0.1.json"


class MemoryAuditLogger:
    def __init__(self) -> None:
        self.events: list[AuditEvent] = []

    def log(self, event: AuditEvent) -> Path:
        self.events.append(event)
        return Path("logs/memory.log")


@pytest.fixture
def isolated_stores(
    tmp_path: Path,
) -> tuple[
    LiveResearchResponseStore,
    LiveContactOptInStore,
    LiveCaptureBatchRegistry,
]:
    tag = f"_pytest_{tmp_path.name}"
    research_root = LiveResearchResponseStore.DEFAULT_ROOT / tag
    contact_root = LiveContactOptInStore.DEFAULT_ROOT / tag
    registry_root = LiveCaptureBatchRegistry.DEFAULT_ROOT / tag

    stores = (
        LiveResearchResponseStore(research_root),
        LiveContactOptInStore(contact_root),
        LiveCaptureBatchRegistry(registry_root),
    )
    yield stores

    for root in (research_root, contact_root, registry_root):
        shutil.rmtree(root, ignore_errors=True)


def deterministic_token(prefix: str) -> str:
    return {
        "FPVPT": "FPVPT-stage4jbtest",
        "FPVS": "FPVS-stage4jbtest",
        "public-form": "public-form-stage4jbtest",
    }[prefix]


def second_token(prefix: str) -> str:
    return {
        "FPVPT": "FPVPT-stage4jbtest2",
        "FPVS": "FPVS-stage4jbtest2",
        "public-form": "public-form-stage4jbtest2",
    }[prefix]


def capture_id(prefix: str) -> str:
    return f"{prefix}-capture-test"


def make_service(
    stores: tuple[
        LiveResearchResponseStore,
        LiveContactOptInStore,
        LiveCaptureBatchRegistry,
    ],
    *,
    audit: MemoryAuditLogger | None = None,
) -> LiveCaptureStorageService:
    research_store, contact_store, registry = stores
    return LiveCaptureStorageService(
        research_store=research_store,
        contact_store=contact_store,
        batch_registry=registry,
        audit_logger=audit or MemoryAuditLogger(),  # type: ignore[arg-type]
        contract_path=CONTRACT_PATH,
        storage_policy_path=STORAGE_POLICY_PATH,
    )


def contract() -> dict[str, Any]:
    return json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))


def valid_research_request() -> dict[str, Any]:
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


def valid_contact_request() -> dict[str, Any]:
    return {
        "participant_token": "FPVPT-stage4jbtest",
        "contact_name": "",
        "contact_method": "email",
        "contact_value": "preview@example.invalid",
        "requested_action": "interview",
        "consent_to_contact": True,
    }


def test_gate_keeps_all_protected_actions_false() -> None:
    gate = json.loads(GATE_PATH.read_text(encoding="utf-8"))
    assert gate["storage_mode"] == "synthetic_test_only"
    assert gate["network_listener_present"] is False
    assert gate["live_server_side_storage_enabled"] is False
    assert gate["live_contact_collection_enabled"] is False
    assert not any(gate["protected_actions"].values())


def test_policy_requires_separate_roots() -> None:
    policy = json.loads(STORAGE_POLICY_PATH.read_text(encoding="utf-8"))
    roots = policy["runtime_roots"]
    assert len(set(roots.values())) == 3
    assert policy["separation"]["participant_token_is_only_join_key"] is True
    assert policy["separation"]["direct_identifiers_allowed_in_research_store"] is False


def test_controlled_research_store_rejects_outside_root(tmp_path: Path) -> None:
    with pytest.raises(FirstPartyValidationStorageError):
        LiveResearchResponseStore(tmp_path / "outside")


def test_controlled_contact_store_rejects_outside_root(tmp_path: Path) -> None:
    with pytest.raises(FirstPartyValidationStorageError):
        LiveContactOptInStore(tmp_path / "outside")


def test_research_and_contact_roots_are_physically_separate(
    isolated_stores: tuple[
        LiveResearchResponseStore,
        LiveContactOptInStore,
        LiveCaptureBatchRegistry,
    ],
) -> None:
    service = make_service(isolated_stores)
    assert service.research_store.root != service.contact_store.root
    assert service.research_store.root != service.batch_registry.root
    assert service.contact_store.root != service.batch_registry.root


def test_research_write_is_synthetic_and_not_stage4g_handoff(
    isolated_stores: tuple[
        LiveResearchResponseStore,
        LiveContactOptInStore,
        LiveCaptureBatchRegistry,
    ],
) -> None:
    service = make_service(isolated_stores)
    receipt = service.store_research_request(
        valid_research_request(),
        token_factory=deterministic_token,
        capture_id_factory=capture_id,
    )
    records = service.research_store.read(
        service.research_store.path_for("EOP-0001-FPV-20260805")
    )
    assert receipt.storage_mode == "synthetic_test_only"
    assert receipt.stage4g_handoff_allowed is False
    assert receipt.validation_log_import_allowed is False
    assert len(records) == 1
    assert records[0]["live_evidence_eligible"] is False
    assert records[0]["stage4g_handoff_allowed"] is False
    assert records[0]["validation_log_import_allowed"] is False


@pytest.mark.parametrize(
    "identifier",
    [
        "name",
        "full_name",
        "first_name",
        "last_name",
        "email",
        "phone",
        "address",
        "postcode",
        "ip_address",
        "device_id",
        "cookie",
    ],
)
def test_research_record_has_no_direct_identifier_key(
    isolated_stores: tuple[
        LiveResearchResponseStore,
        LiveContactOptInStore,
        LiveCaptureBatchRegistry,
    ],
    identifier: str,
) -> None:
    service = make_service(isolated_stores)
    service.store_research_request(
        valid_research_request(),
        token_factory=deterministic_token,
    )
    record = service.research_store.read(
        service.research_store.path_for("EOP-0001-FPV-20260805")
    )[0]

    def keys(value: Any) -> list[str]:
        found: list[str] = []
        if isinstance(value, dict):
            for key, child in value.items():
                found.append(key.lower())
                found.extend(keys(child))
        elif isinstance(value, list):
            for child in value:
                found.extend(keys(child))
        return found

    assert identifier not in keys(record)


def test_duplicate_research_token_fails_closed(
    isolated_stores: tuple[
        LiveResearchResponseStore,
        LiveContactOptInStore,
        LiveCaptureBatchRegistry,
    ],
) -> None:
    service = make_service(isolated_stores)
    service.store_research_request(
        valid_research_request(),
        token_factory=deterministic_token,
    )
    with pytest.raises(
        LiveCaptureStorageError,
        match="duplicate_research_submission_id|duplicate_research_participant_token",
    ):
        service.store_research_request(
            valid_research_request(),
            token_factory=deterministic_token,
        )


def test_distinct_server_ids_allow_same_answers_from_two_people(
    isolated_stores: tuple[
        LiveResearchResponseStore,
        LiveContactOptInStore,
        LiveCaptureBatchRegistry,
    ],
) -> None:
    service = make_service(isolated_stores)
    service.store_research_request(
        valid_research_request(),
        token_factory=deterministic_token,
    )
    service.store_research_request(
        valid_research_request(),
        token_factory=second_token,
    )
    records = service.research_store.read(
        service.research_store.path_for("EOP-0001-FPV-20260805")
    )
    assert len(records) == 2


def test_contact_requires_known_research_token(
    isolated_stores: tuple[
        LiveResearchResponseStore,
        LiveContactOptInStore,
        LiveCaptureBatchRegistry,
    ],
) -> None:
    service = make_service(isolated_stores)
    with pytest.raises(
        LiveCaptureStorageError,
        match="unknown_research_participant_token",
    ):
        service.store_contact_request(valid_contact_request())


def test_contact_writes_only_after_research_token_exists(
    isolated_stores: tuple[
        LiveResearchResponseStore,
        LiveContactOptInStore,
        LiveCaptureBatchRegistry,
    ],
) -> None:
    service = make_service(isolated_stores)
    service.store_research_request(
        valid_research_request(),
        token_factory=deterministic_token,
    )
    receipt = service.store_contact_request(
        valid_contact_request(),
        capture_id_factory=capture_id,
    )
    records = service.contact_store.read(
        service.contact_store.path_for("EOP-0001-FPV-20260805")
    )
    assert receipt.record_type == "contact"
    assert len(records) == 1
    assert records[0]["stage4g_research_capture_allowed"] is False
    assert records[0]["stage4g_handoff_allowed"] is False
    assert records[0]["validation_log_import_allowed"] is False


def test_contact_name_remains_optional(
    isolated_stores: tuple[
        LiveResearchResponseStore,
        LiveContactOptInStore,
        LiveCaptureBatchRegistry,
    ],
) -> None:
    service = make_service(isolated_stores)
    service.store_research_request(
        valid_research_request(),
        token_factory=deterministic_token,
    )
    service.store_contact_request(valid_contact_request())
    record = service.contact_store.read(
        service.contact_store.path_for("EOP-0001-FPV-20260805")
    )[0]
    assert record["contact_name"] == ""


def test_contact_never_appears_in_research_store(
    isolated_stores: tuple[
        LiveResearchResponseStore,
        LiveContactOptInStore,
        LiveCaptureBatchRegistry,
    ],
) -> None:
    service = make_service(isolated_stores)
    service.store_research_request(
        valid_research_request(),
        token_factory=deterministic_token,
    )
    service.store_contact_request(valid_contact_request())
    research_bytes = service.research_store.path_for(
        "EOP-0001-FPV-20260805"
    ).read_text(encoding="utf-8")
    assert "preview@example.invalid" not in research_bytes
    assert '"contact_value"' not in research_bytes


def test_duplicate_contact_opt_in_fails_closed(
    isolated_stores: tuple[
        LiveResearchResponseStore,
        LiveContactOptInStore,
        LiveCaptureBatchRegistry,
    ],
) -> None:
    service = make_service(isolated_stores)
    service.store_research_request(
        valid_research_request(),
        token_factory=deterministic_token,
    )
    service.store_contact_request(valid_contact_request())
    with pytest.raises(LiveCaptureStorageError, match="duplicate_contact_opt_in"):
        service.store_contact_request(valid_contact_request())


def test_registry_contains_no_raw_contact_value(
    isolated_stores: tuple[
        LiveResearchResponseStore,
        LiveContactOptInStore,
        LiveCaptureBatchRegistry,
    ],
) -> None:
    service = make_service(isolated_stores)
    service.store_research_request(
        valid_research_request(),
        token_factory=deterministic_token,
    )
    service.store_contact_request(valid_contact_request())
    registry = service.batch_registry.registry_path.read_text(encoding="utf-8")
    assert "preview@example.invalid" not in registry
    assert "FPVPT-stage4jbtest" not in registry


def test_audit_minimises_contact_data(
    isolated_stores: tuple[
        LiveResearchResponseStore,
        LiveContactOptInStore,
        LiveCaptureBatchRegistry,
    ],
) -> None:
    audit = MemoryAuditLogger()
    service = make_service(isolated_stores, audit=audit)
    service.store_research_request(
        valid_research_request(),
        token_factory=deterministic_token,
    )
    service.store_contact_request(valid_contact_request())
    payload = json.dumps(
        [event.details for event in audit.events],
        sort_keys=True,
    )
    assert "preview@example.invalid" not in payload
    assert "FPVPT-stage4jbtest" not in payload
    assert "contact_value" not in payload
    assert "contact_name" not in payload


def test_research_write_rolls_back_when_registry_write_fails(
    isolated_stores: tuple[
        LiveResearchResponseStore,
        LiveContactOptInStore,
        LiveCaptureBatchRegistry,
    ],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = make_service(isolated_stores)

    def fail_registry(*args: Any, **kwargs: Any) -> Path:
        raise RuntimeError("simulated registry failure")

    monkeypatch.setattr(service.batch_registry, "append_many", fail_registry)
    with pytest.raises(RuntimeError, match="simulated registry failure"):
        service.store_research_request(
            valid_research_request(),
            token_factory=deterministic_token,
        )
    path = service.research_store.path_for("EOP-0001-FPV-20260805")
    assert not path.exists()


def test_contact_write_rolls_back_when_registry_write_fails(
    isolated_stores: tuple[
        LiveResearchResponseStore,
        LiveContactOptInStore,
        LiveCaptureBatchRegistry,
    ],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = make_service(isolated_stores)
    service.store_research_request(
        valid_research_request(),
        token_factory=deterministic_token,
    )

    original = service.batch_registry.append_many

    def fail_contact_registry(path: Path, payloads: list[dict[str, Any]]) -> Path:
        if payloads and payloads[0].get("record_type") == "contact":
            raise RuntimeError("simulated contact registry failure")
        return original(path, payloads)

    monkeypatch.setattr(
        service.batch_registry,
        "append_many",
        fail_contact_registry,
    )
    with pytest.raises(RuntimeError, match="simulated contact registry failure"):
        service.store_contact_request(valid_contact_request())
    path = service.contact_store.path_for("EOP-0001-FPV-20260805")
    assert not path.exists()


def test_retention_is_metadata_only_and_not_live_approved(
    isolated_stores: tuple[
        LiveResearchResponseStore,
        LiveContactOptInStore,
        LiveCaptureBatchRegistry,
    ],
) -> None:
    service = make_service(isolated_stores)
    service.store_research_request(
        valid_research_request(),
        token_factory=deterministic_token,
    )
    record = service.research_store.read(
        service.research_store.path_for("EOP-0001-FPV-20260805")
    )[0]
    assert record["retention_status"] == "NOT_APPROVED_FOR_LIVE_USE"
    assert record["automated_deletion_enabled"] is False
    assert record["deletion_requires_human_review"] is True


def test_registry_is_identifier_minimised(
    isolated_stores: tuple[
        LiveResearchResponseStore,
        LiveContactOptInStore,
        LiveCaptureBatchRegistry,
    ],
) -> None:
    service = make_service(isolated_stores)
    service.store_research_request(
        valid_research_request(),
        token_factory=deterministic_token,
    )
    registry_record = LiveCaptureBatchRegistry.read(
        service.batch_registry.registry_path
    )[0]
    assert "participant_token" not in registry_record
    assert "participant_link_hash" in registry_record
