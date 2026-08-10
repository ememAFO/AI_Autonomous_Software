"""Append-only storage for Stage 4F mapping packets and imports."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


class VerifiedIntakeMappingStorageError(ValueError):
    """Raised when Stage 4F storage violates a controlled boundary."""


class _ControlledJsonlStore:
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
        if self.root != self.expected_root and not self._is_within(
            self.root,
            self.expected_root,
        ):
            raise VerifiedIntakeMappingStorageError(
                f"Store must remain inside {self.expected_root}"
            )
        self.root.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _safe_component(value: str) -> str:
        safe = "".join(
            character
            for character in value
            if character.isalnum() or character in {"-", "_"}
        ).strip("._")
        if not safe:
            raise VerifiedIntakeMappingStorageError(
                "Invalid storage identifier"
            )
        return safe[:120]

    @staticmethod
    def _append(path: Path, payload: dict[str, Any]) -> Path:
        with path.open("a", encoding="utf-8") as handle:
            handle.write(
                json.dumps(payload, ensure_ascii=False) + "\n"
            )
        return path

    @staticmethod
    def _read(path: Path) -> list[dict[str, Any]]:
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
                raise VerifiedIntakeMappingStorageError(
                    f"Invalid JSONL at {path}:{line_number}"
                ) from exc
            if not isinstance(record, dict):
                raise VerifiedIntakeMappingStorageError(
                    f"JSONL record is not an object at {path}:{line_number}"
                )
            records.append(record)
        return records

    @staticmethod
    def _is_within(path: Path, root: Path) -> bool:
        try:
            path.relative_to(root)
            return True
        except ValueError:
            return False


class MappingPacketRegistry(_ControlledJsonlStore):
    DEFAULT_ROOT = Path(
        "data/research/verified_intake_mapping_packets"
    )

    def __init__(
        self,
        root: str | Path = DEFAULT_ROOT,
    ) -> None:
        super().__init__(
            root=root,
            expected_relative_root=self.DEFAULT_ROOT,
        )
        self.registry_path = self.root / "registry.jsonl"

    def append(
        self,
        *,
        packet_id: str,
        packet_hash: str,
        workflow_id: str,
        packet_path: str,
        approval_template_path: str,
        policy_id: str,
        created_at: str,
    ) -> Path:
        if self.find(packet_id) is not None:
            raise VerifiedIntakeMappingStorageError(
                "Mapping packet ID is already registered"
            )
        return self._append(
            self.registry_path,
            {
                "packet_id": packet_id,
                "packet_hash": packet_hash,
                "workflow_id": workflow_id,
                "packet_path": packet_path,
                "approval_template_path": approval_template_path,
                "policy_id": policy_id,
                "created_at": created_at,
                "registered_at": datetime.now(UTC).isoformat(),
            },
        )

    def find(self, packet_id: str) -> dict[str, Any] | None:
        matches = [
            record
            for record in self._read(self.registry_path)
            if record.get("packet_id") == packet_id
        ]
        if len(matches) > 1:
            raise VerifiedIntakeMappingStorageError(
                "Mapping packet registry contains duplicate IDs"
            )
        return matches[0] if matches else None


class ValidationEvidenceImportRegistry(_ControlledJsonlStore):
    DEFAULT_ROOT = Path(
        "data/research/validation_evidence_imports"
    )

    def __init__(
        self,
        root: str | Path = DEFAULT_ROOT,
    ) -> None:
        super().__init__(
            root=root,
            expected_relative_root=self.DEFAULT_ROOT,
        )

    def path_for(self, workflow_id: str) -> Path:
        return self.root / (
            self._safe_component(workflow_id) + ".jsonl"
        )

    def append(self, payload: dict[str, Any]) -> Path:
        workflow_id = str(
            payload.get("workflow_id", "")
        ).strip()
        packet_id = str(payload.get("packet_id", "")).strip()
        if not workflow_id or not packet_id:
            raise VerifiedIntakeMappingStorageError(
                "Import record requires workflow_id and packet_id"
            )
        if self.has_packet(packet_id):
            raise VerifiedIntakeMappingStorageError(
                "Mapping packet was already imported"
            )
        return self._append(
            self.path_for(workflow_id),
            dict(payload),
        )

    def has_packet(self, packet_id: str) -> bool:
        for path in self.root.glob("*.jsonl"):
            if any(
                record.get("packet_id") == packet_id
                for record in self._read(path)
            ):
                return True
        return False
