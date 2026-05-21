from __future__ import annotations

from dataclasses import dataclass
import subprocess
from pathlib import Path


class SandboxError(Exception):
    pass


@dataclass(frozen=True)
class SandboxResult:
    command: tuple[str, ...]
    returncode: int
    stdout: str
    stderr: str


class SandboxRunner:
    """Constrained local runner for tests and scans.

    This is deliberately small. Agent Zero can call this layer later, but it should
    not get unrestricted shell/root/sudo access.
    """

    DEFAULT_ALLOWED = {"pytest", "python", "ruff", "mypy", "bandit", "pip-audit", "semgrep"}
    BLOCKED_TOKENS = {"sudo", "su", "rm", "chmod", "chown", "curl", "wget", "ssh", "scp"}

    def __init__(self, project_root: str | Path, allowed_commands: set[str] | None = None) -> None:
        self.project_root = Path(project_root).resolve()
        self.allowed_commands = allowed_commands or self.DEFAULT_ALLOWED

    def run(self, command: list[str], timeout_seconds: int = 60) -> SandboxResult:
        if not command:
            raise SandboxError("Empty command is not allowed")
        executable = Path(command[0]).name
        if executable not in self.allowed_commands:
            raise SandboxError(f"Command not allowed: {executable}")
        if any(token in self.BLOCKED_TOKENS for token in command):
            raise SandboxError(f"Blocked dangerous token in command: {command}")
        completed = subprocess.run(
            command,
            cwd=self.project_root,
            text=True,
            capture_output=True,
            timeout=timeout_seconds,
            check=False,
        )
        return SandboxResult(tuple(command), completed.returncode, completed.stdout, completed.stderr)
