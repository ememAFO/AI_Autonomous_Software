from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
import json
from typing import Any


@dataclass(frozen=True)
class AuditEvent:
    event_type: str
    actor: str
    action: str
    outcome: str
    details: dict[str, Any]
    timestamp: str


class AuditLogger:
    """Append-only JSONL audit logger for agent and policy actions."""

    def __init__(self, log_path: str | Path = "logs/audit.jsonl") -> None:
        self.log_path = Path(log_path)
        self.log_path.parent.mkdir(parents=True, exist_ok=True)

    def record(
        self,
        *,
        event_type: str,
        actor: str,
        action: str,
        outcome: str,
        details: dict[str, Any] | None = None,
    ) -> AuditEvent:
        event = AuditEvent(
            event_type=event_type,
            actor=actor,
            action=action,
            outcome=outcome,
            details=details or {},
            timestamp=datetime.now(timezone.utc).isoformat(),
        )
        with self.log_path.open("a", encoding="utf-8") as file:
            file.write(json.dumps(asdict(event), sort_keys=True) + "\n")
        return event
