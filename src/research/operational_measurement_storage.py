"""Append-only storage for Stage 4G v0.2 operational measurements."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from uuid import uuid4


class OperationalMeasurementStorageError(ValueError):
    """Raised when measurement storage violates a controlled boundary."""


class ControlledMeasurementStore:
    """JSONL storage restricted to one project-relative root."""

    def __init__(
        self,
        *,
        root: str | Path,
        expected_relative_root: Path,
    ) -> None:
        self.project_root = Path.cwd().resolve()
        self.expected_root = (
            self.project_root / expected_relative_root
        ).resolve()
        self.root = Path(root).resolve()
        if not self._is_within(self.root, self.expected_root):
            raise OperationalMeasurementStorageError(
                f"Store must remain inside {self.expected_root}"
            )
        self.root.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def safe_component(value: str) -> str:
        safe = "".join(
            character
            for character in value
            if character.isalnum() or character in {"-", "_"}
        ).strip("._")
        if not safe:
            raise OperationalMeasurementStorageError(
                "Invalid storage identifier"
            )
        return safe[:120]

    def path_for(self, identifier: str) -> Path:
        return self.root / f"{self.safe_component(identifier)}.jsonl"

    @staticmethod
    def read(path: Path) -> list[dict[str, Any]]:
        if not path.exists():
            return []
        records: list[dict[str, Any]] = []
        for line_number, line in enumerate(
            path.read_text(encoding="utf-8").splitlines(),
            start=1,
        ):
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                raise OperationalMeasurementStorageError(
                    f"Invalid JSONL at {path}:{line_number}"
                ) from exc
            if not isinstance(record, dict):
                raise OperationalMeasurementStorageError(
                    "JSONL record is not an object at "
                    f"{path}:{line_number}"
                )
            records.append(record)
        return records

    @staticmethod
    def append_many(
        path: Path,
        payloads: list[dict[str, Any]],
    ) -> Path:
        if not payloads:
            return path
        path.parent.mkdir(parents=True, exist_ok=True)
        existing = path.read_bytes() if path.exists() else b""
        addition = "".join(
            json.dumps(payload, ensure_ascii=False, sort_keys=True)
            + "\n"
            for payload in payloads
        ).encode()
        temporary = path.with_name(
            f".{path.name}.{uuid4().hex}.tmp"
        )
        temporary.write_bytes(existing + addition)
        temporary.replace(path)
        return path

    @staticmethod
    def snapshot(path: Path) -> bytes | None:
        return path.read_bytes() if path.exists() else None

    @staticmethod
    def restore(path: Path, snapshot: bytes | None) -> None:
        if snapshot is None:
            if path.exists():
                path.unlink()
            return
        temporary = path.with_name(
            f".{path.name}.{uuid4().hex}.restore"
        )
        temporary.write_bytes(snapshot)
        temporary.replace(path)

    @staticmethod
    def _is_within(path: Path, root: Path) -> bool:
        try:
            path.relative_to(root)
            return True
        except ValueError:
            return False


class OperationalMeasurementCandidateStore(
    ControlledMeasurementStore
):
    DEFAULT_ROOT = Path(
        "data/research/operational_measurement_candidates"
    )

    def __init__(self, root: str | Path = DEFAULT_ROOT) -> None:
        super().__init__(
            root=root,
            expected_relative_root=self.DEFAULT_ROOT,
        )


class OperationalMeasurementCaptureRegistry(
    ControlledMeasurementStore
):
    DEFAULT_ROOT = Path(
        "data/research/operational_measurement_capture_batches"
    )

    def __init__(self, root: str | Path = DEFAULT_ROOT) -> None:
        super().__init__(
            root=root,
            expected_relative_root=self.DEFAULT_ROOT,
        )
        self.registry_path = self.root / "registry.jsonl"

    def has_batch(self, batch_id: str) -> bool:
        return any(
            record.get("batch_id") == batch_id
            for record in self.read(self.registry_path)
        )


class OperationalMeasurementPacketRegistry(
    ControlledMeasurementStore
):
    DEFAULT_ROOT = Path(
        "data/research/operational_measurement_review_packets"
    )

    def __init__(self, root: str | Path = DEFAULT_ROOT) -> None:
        super().__init__(
            root=root,
            expected_relative_root=self.DEFAULT_ROOT,
        )
        self.registry_path = self.root / "registry.jsonl"

    def find(self, packet_id: str) -> dict[str, Any] | None:
        matches = [
            record
            for record in self.read(self.registry_path)
            if record.get("packet_id") == packet_id
        ]
        if len(matches) > 1:
            raise OperationalMeasurementStorageError(
                "Packet registry contains duplicate packet IDs"
            )
        return matches[0] if matches else None


class OperationalMeasurementDecisionStore(
    ControlledMeasurementStore
):
    DEFAULT_ROOT = Path(
        "data/research/operational_measurement_review_decisions"
    )

    def __init__(self, root: str | Path = DEFAULT_ROOT) -> None:
        super().__init__(
            root=root,
            expected_relative_root=self.DEFAULT_ROOT,
        )

    def has_packet(self, packet_id: str) -> bool:
        for path in self.root.glob("*.jsonl"):
            if any(
                record.get("packet_id") == packet_id
                for record in self.read(path)
            ):
                return True
        return False


class OperationalMeasurementVerifiedStore(
    ControlledMeasurementStore
):
    DEFAULT_ROOT = Path(
        "data/research/operational_measurement_verified"
    )

    def __init__(self, root: str | Path = DEFAULT_ROOT) -> None:
        super().__init__(
            root=root,
            expected_relative_root=self.DEFAULT_ROOT,
        )
