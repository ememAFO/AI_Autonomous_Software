import json
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


class AuditLoggerError(Exception):
    pass


@dataclass(frozen=True)
class AuditEvent:
    action: str
    status: str
    details: dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())


class AuditLogger:
    """
    Writes append-only JSONL audit logs.

    Security rules:
    - Logs must stay inside the logs directory.
    - One event per line.
    - Secrets are redacted.
    - Path traversal is blocked.
    """

    DEFAULT_LOG_PATH = Path("logs/audit.log")

    SECRET_KEYS = {
        "password",
        "secret",
        "token",
        "api_key",
        "apikey",
        "access_token",
        "refresh_token",
        "authorization",
        "cookie",
    }

    def __init__(self, log_path: str | Path = DEFAULT_LOG_PATH):
        self.log_path = self._validate_log_path(Path(log_path))
        self.log_path.parent.mkdir(parents=True, exist_ok=True)

    def log(self, event: AuditEvent) -> Path:
        sanitized_event = AuditEvent(
            action=event.action,
            status=event.status,
            details=self._redact_secrets(event.details),
            timestamp=event.timestamp,
        )

        line = json.dumps(asdict(sanitized_event), sort_keys=True)

        with self.log_path.open("a", encoding="utf-8") as file:
            file.write(line + "\n")

        return self.log_path

    def _validate_log_path(self, log_path: Path) -> Path:
        resolved = log_path.resolve()
        project_root = Path.cwd().resolve()
        logs_root = (project_root / "logs").resolve()

        if not str(resolved).startswith(str(logs_root)):
            raise AuditLoggerError("Audit log path must stay inside the logs folder")

        if resolved.suffix != ".log":
            raise AuditLoggerError("Audit log file must use .log extension")

        return resolved

    def _redact_secrets(self, data: dict[str, Any]) -> dict[str, Any]:
        redacted: dict[str, Any] = {}

        for key, value in data.items():
            if self._is_secret_key(key):
                redacted[key] = "[REDACTED]"
            elif isinstance(value, dict):
                redacted[key] = self._redact_secrets(value)
            else:
                redacted[key] = value

        return redacted

    def _is_secret_key(self, key: str) -> bool:
        lowered = key.lower()
        return any(secret_key in lowered for secret_key in self.SECRET_KEYS)
