from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


class PermissionError(Exception):
    pass


@dataclass(frozen=True)
class PermissionPolicy:
    project_root: Path
    protected_dirs: tuple[str, ...] = ("protected",)
    blocked_paths: tuple[str, ...] = (".env", "secrets", "credentials")
    editable_dirs: tuple[str, ...] = ("src", "tests", "reports", "sandbox", "docs", "logs")

    def __post_init__(self) -> None:
        object.__setattr__(self, "project_root", Path(self.project_root).resolve())

    def resolve_inside_project(self, target: str | Path) -> Path:
        path = Path(target)
        resolved = (self.project_root / path).resolve() if not path.is_absolute() else path.resolve()
        if self.project_root not in resolved.parents and resolved != self.project_root:
            raise PermissionError(f"Path escapes project root: {target}")
        return resolved

    def assert_edit_allowed(self, target: str | Path) -> Path:
        resolved = self.resolve_inside_project(target)
        relative = resolved.relative_to(self.project_root)
        parts = relative.parts
        if not parts:
            raise PermissionError("Project root itself cannot be edited by agents")
        if parts[0] in self.protected_dirs:
            raise PermissionError(f"Protected file path cannot be edited: {relative}")
        lower = str(relative).lower()
        if any(blocked in lower for blocked in self.blocked_paths):
            raise PermissionError(f"Sensitive path cannot be edited: {relative}")
        if parts[0] not in self.editable_dirs:
            raise PermissionError(f"Path is not in an agent-editable folder: {relative}")
        return resolved
