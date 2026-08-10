"""Append-only candidate queue for unapproved web evidence."""

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.adapters.research_adapter import EvidenceCandidate


class EvidenceCandidateQueueError(ValueError):
    pass


class EvidenceCandidateQueue:
    DEFAULT_ROOT = Path("data/hound/evidence_candidates")

    def __init__(self, root: str | Path = DEFAULT_ROOT) -> None:
        self.root = self._validate_root(Path(root))
        self.root.mkdir(parents=True, exist_ok=True)

    def append(self, candidate: EvidenceCandidate) -> Path:
        workflow = self._safe_component(candidate.workflow_id)
        path = self.root / f"{workflow}.jsonl"
        record: dict[str, Any] = asdict(candidate)
        record["status"] = candidate.status.value
        record["queued_at"] = datetime.now(timezone.utc).isoformat()
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
        return path

    @staticmethod
    def _validate_root(root: Path) -> Path:
        project_root = Path.cwd().resolve()
        expected = (project_root / "data" / "hound" / "evidence_candidates").resolve()
        resolved = root.resolve()
        if resolved != expected and not str(resolved).startswith(str(expected) + "/"):
            raise EvidenceCandidateQueueError(
                "Candidate queue must stay inside "
                "data/hound/evidence_candidates"
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
            raise EvidenceCandidateQueueError("Invalid workflow identifier")
        return safe[:100]
