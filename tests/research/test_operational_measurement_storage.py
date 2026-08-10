from __future__ import annotations

from pathlib import Path

import pytest

from src.research.operational_measurement_storage import (
    OperationalMeasurementCaptureRegistry,
    OperationalMeasurementPacketRegistry,
    OperationalMeasurementStorageError,
)


def test_storage_rejects_path_outside_controlled_root(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    with pytest.raises(OperationalMeasurementStorageError):
        OperationalMeasurementCaptureRegistry(
            tmp_path / "outside"
        )


def test_capture_registry_detects_processed_batch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    registry = OperationalMeasurementCaptureRegistry()
    registry.append_many(
        registry.registry_path,
        [{"batch_id": "B-1"}],
    )
    assert registry.has_batch("B-1") is True
    assert registry.has_batch("B-2") is False


def test_packet_registry_finds_one_packet(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    registry = OperationalMeasurementPacketRegistry()
    registry.append_many(
        registry.registry_path,
        [{"packet_id": "P-1", "packet_hash": "hash"}],
    )
    assert registry.find("P-1") is not None
    assert registry.find("P-2") is None
