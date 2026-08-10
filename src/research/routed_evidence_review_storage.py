"""Append-only storage for Stage 4E packets, decisions and verified intake."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


class RoutedEvidenceReviewStorageError(ValueError):
    """Raised when Stage 4E storage violates its controlled path."""


class _AppendOnlyJsonlStore:
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
        self.root = self._validate_root(Path(root))
        self.root.mkdir(parents=True, exist_ok=True)

    def _validate_root(self, root: Path) -> Path:
        resolved = root.resolve()
        if resolved != self.expected_root and not self._is_within(
            resolved,
            self.expected_root,
        ):
            raise RoutedEvidenceReviewStorageError(
                f"Store must stay inside {self.expected_root}"
            )
        return resolved

    @staticmethod
    def _safe_component(value: str) -> str:
        safe = "".join(
            character
            for character in value
            if character.isalnum() or character in {"-", "_"}
        ).strip("._")
        if not safe:
            raise RoutedEvidenceReviewStorageError(
                "Invalid storage identifier"
            )
        return safe[:100]

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
                item = json.loads(line)
            except json.JSONDecodeError as exc:
                raise RoutedEvidenceReviewStorageError(
                    f"Invalid JSONL at {path}:{line_number}"
                ) from exc
            if not isinstance(item, dict):
                raise RoutedEvidenceReviewStorageError(
                    f"JSONL record is not an object at {path}:{line_number}"
                )
            records.append(item)
        return records

    @staticmethod
    def _is_within(path: Path, root: Path) -> bool:
        try:
            path.relative_to(root)
            return True
        except ValueError:
            return False


class EvidenceReviewPacketRegistry(_AppendOnlyJsonlStore):
    DEFAULT_ROOT = Path("data/research/evidence_review_packets")

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
        packet,
        packet_json_path: str,
        packet_markdown_path: str,
        decision_template_path: str,
    ) -> Path:
        if self.find(packet.packet_id) is not None:
            raise RoutedEvidenceReviewStorageError(
                "Packet ID is already registered"
            )
        return self._append(
            self.registry_path,
            {
                "packet_id": packet.packet_id,
                "packet_hash": packet.packet_hash,
                "workflow_id": packet.workflow_id,
                "candidate_file": packet.candidate_file,
                "candidate_file_hash": (
                    packet.candidate_file_hash
                ),
                "packet_json_path": packet_json_path,
                "packet_markdown_path": packet_markdown_path,
                "decision_template_path": decision_template_path,
                "policy_version": packet.policy_version,
                "created_at": packet.created_at,
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
            raise RoutedEvidenceReviewStorageError(
                "Packet registry contains duplicate packet IDs"
            )
        return matches[0] if matches else None


class EvidenceReviewDecisionRegistry(_AppendOnlyJsonlStore):
    DEFAULT_ROOT = Path("data/research/evidence_review_decisions")

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
        if not workflow_id:
            raise RoutedEvidenceReviewStorageError(
                "Decision record requires workflow_id"
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


class VerifiedEvidenceIntakeQueue(_AppendOnlyJsonlStore):
    DEFAULT_ROOT = Path("data/research/verified_evidence_intake")

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
        review_id = str(payload.get("review_id", "")).strip()
        content_hash = str(
            payload.get("content_hash", "")
        ).strip()
        canonical_url = str(
            payload.get("canonical_url", "")
        ).strip()
        if not all(
            (workflow_id, review_id, content_hash, canonical_url)
        ):
            raise RoutedEvidenceReviewStorageError(
                "Verified intake record lacks required provenance"
            )
        path = self.path_for(workflow_id)
        existing = self._read(path)
        for record in existing:
            if record.get("review_id") == review_id:
                raise RoutedEvidenceReviewStorageError(
                    "Review ID is already promoted"
                )
            if (
                record.get("content_hash") == content_hash
                or record.get("canonical_url") == canonical_url
            ):
                raise RoutedEvidenceReviewStorageError(
                    "Duplicate verified evidence promotion blocked"
                )
        return self._append(path, dict(payload))
