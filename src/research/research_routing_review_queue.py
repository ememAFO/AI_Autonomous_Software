"""Append-only human-review queue for unsupported or failed source routes."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


class ResearchRoutingReviewQueueError(ValueError):
    """Raised when review storage violates the controlled path."""


@dataclass(frozen=True)
class RoutingReviewRecord:
    workflow_id: str
    source_id: str
    url: str
    route_target: str
    reason: str
    error: str = ""
    details: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(
        default_factory=lambda: datetime.now(UTC).isoformat()
    )


class ResearchRoutingReviewQueue:
    DEFAULT_ROOT = Path("data/research/routing_review")

    def __init__(self, root: str | Path = DEFAULT_ROOT) -> None:
        self.root = self._validate_root(Path(root))
        self.root.mkdir(parents=True, exist_ok=True)

    def append(self, record: RoutingReviewRecord) -> Path:
        workflow = self._safe_component(record.workflow_id)
        path = self.root / f"{workflow}.jsonl"
        with path.open("a", encoding="utf-8") as handle:
            handle.write(
                json.dumps(asdict(record), ensure_ascii=False) + "\n"
            )
        return path

    @staticmethod
    def _validate_root(root: Path) -> Path:
        project_root = Path.cwd().resolve()
        expected = (
            project_root / "data" / "research" / "routing_review"
        ).resolve()
        resolved = root.resolve()
        if resolved != expected and not str(resolved).startswith(
            str(expected) + "/"
        ):
            raise ResearchRoutingReviewQueueError(
                "Routing review queue must stay inside "
                "data/research/routing_review"
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
            raise ResearchRoutingReviewQueueError(
                "Invalid workflow identifier"
            )
        return safe[:100]
