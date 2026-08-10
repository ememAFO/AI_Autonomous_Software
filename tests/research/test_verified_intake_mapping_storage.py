from __future__ import annotations

from pathlib import Path

import pytest

from src.research.verified_intake_mapping_storage import (
    MappingPacketRegistry,
    ValidationEvidenceImportRegistry,
    VerifiedIntakeMappingStorageError,
)


def test_packet_registry_is_append_only(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    registry = MappingPacketRegistry()
    registry.append(
        packet_id="P-1",
        packet_hash="hash",
        workflow_id="WF-1",
        packet_path="reports/research/verified_intake_mappings/p.json",
        approval_template_path=(
            "reports/research/verified_intake_mappings/a.json"
        ),
        policy_id="POL-1",
        created_at="2026-08-05T00:00:00+00:00",
    )
    with pytest.raises(VerifiedIntakeMappingStorageError):
        registry.append(
            packet_id="P-1",
            packet_hash="hash",
            workflow_id="WF-1",
            packet_path="p",
            approval_template_path="a",
            policy_id="POL-1",
            created_at="now",
        )


def test_import_registry_detects_packet(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    registry = ValidationEvidenceImportRegistry()
    registry.append(
        {
            "workflow_id": "WF-1",
            "packet_id": "P-1",
        }
    )
    assert registry.has_packet("P-1") is True
    assert registry.has_packet("P-2") is False


def test_storage_outside_controlled_root_is_rejected(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    with pytest.raises(VerifiedIntakeMappingStorageError):
        MappingPacketRegistry(tmp_path / "outside")
