from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


class HermesMemoryError(Exception):
    pass


@dataclass(frozen=True)
class HermesResearchMemoryRecord:
    """
    Structured research memory record.

    This is safe-by-design:
    - no secrets
    - no credentials
    - no shell commands
    - no deployment instructions
    - no protected file write access
    """

    source: str
    industry: str
    pain_point: str
    recommendation: str
    score: float
    report_path: str
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())


class HermesResearchMemoryHook:
    """
    Safe local Hermes memory hook.

    Current version:
    - prepares structured research memory records
    - validates data
    - blocks unsafe paths
    - does not call Hermes live yet
    - does not execute commands
    - does not write outside allowed memory directory

    Later, this can be connected to Hermes through a controlled adapter.
    """

    DEFAULT_MEMORY_DIR = Path("data/hermes/research_memory")

    BLOCKED_TERMS = {
        "password",
        "secret",
        "api_key",
        "access_token",
        "refresh_token",
        "authorization",
        "cookie",
        "stripe_live",
        "private_key",
    }

    def __init__(self, memory_dir: str | Path = DEFAULT_MEMORY_DIR):
        self.memory_dir = self._validate_memory_dir(Path(memory_dir))
        self.memory_dir.mkdir(parents=True, exist_ok=True)

    def build_record(
        self,
        *,
        source: str,
        industry: str,
        pain_point: str,
        recommendation: str,
        score: float,
        report_path: str,
    ) -> HermesResearchMemoryRecord:
        self._validate_text("source", source)
        self._validate_text("industry", industry)
        self._validate_text("pain_point", pain_point)
        self._validate_text("recommendation", recommendation)

        if score < 0 or score > 10:
            raise HermesMemoryError("Score must be between 0 and 10")

        self._validate_report_path(report_path)

        return HermesResearchMemoryRecord(
            source=source,
            industry=industry,
            pain_point=pain_point,
            recommendation=recommendation,
            score=score,
            report_path=report_path,
        )

    def write_record(self, record: HermesResearchMemoryRecord) -> Path:
        safe_filename = self._safe_filename(
            f"{record.industry}_{record.recommendation}_{record.timestamp}"
        )

        memory_path = (self.memory_dir / f"{safe_filename}.json").resolve()

        if not str(memory_path).startswith(str(self.memory_dir)):
            raise HermesMemoryError("Unsafe Hermes memory path detected")

        import json

        memory_path.write_text(
            json.dumps(asdict(record), indent=2, sort_keys=True),
            encoding="utf-8",
        )

        return memory_path

    def _validate_memory_dir(self, memory_dir: Path) -> Path:
        resolved = memory_dir.resolve()
        project_root = Path.cwd().resolve()
        allowed_root = (project_root / "data" / "hermes" / "research_memory").resolve()

        if not str(resolved).startswith(str(allowed_root)):
            raise HermesMemoryError(
                "Hermes memory directory must stay inside data/hermes/research_memory"
            )

        return resolved

    def _validate_report_path(self, report_path: str) -> None:
        path = Path(report_path)

        if path.is_absolute():
            resolved = path.resolve()
        else:
            resolved = (Path.cwd() / path).resolve()

        project_root = Path.cwd().resolve()
        reports_root = (project_root / "reports").resolve()

        if not str(resolved).startswith(str(reports_root)):
            raise HermesMemoryError("Report path must stay inside reports folder")

        if resolved.suffix != ".md":
            raise HermesMemoryError("Report path must point to a Markdown report")

    def _validate_text(self, field_name: str, value: str) -> None:
        if not value or not value.strip():
            raise HermesMemoryError(f"{field_name} cannot be empty")

        lowered = value.lower()

        for blocked_term in self.BLOCKED_TERMS:
            if blocked_term in lowered:
                raise HermesMemoryError(
                    f"{field_name} appears to contain sensitive information"
                )

    def _safe_filename(self, value: str) -> str:
        safe = value.lower().strip().replace(" ", "-").replace(":", "-")
        safe = "".join(char for char in safe if char.isalnum() or char in {"-", "_"})
        return safe[:120] or "hermes-memory-record"
