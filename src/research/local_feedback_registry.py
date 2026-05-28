import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from src.research.local_feedback_research_runner import LocalFeedbackResearchRunResult


class LocalFeedbackRegistryError(Exception):
    pass


@dataclass(frozen=True)
class LocalFeedbackRegistryEntry:
    run_id: str
    source_path: str
    industry: str
    source_type: str
    loaded_count: int
    processed_count: int
    successful_count: int
    blocked_count: int
    local_feedback_report_path: str
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())


@dataclass(frozen=True)
class LocalFeedbackRunRegistry:
    runs: list[LocalFeedbackRegistryEntry] = field(default_factory=list)


class LocalFeedbackRunRegistryWriter:
    """
    Maintains a central index of local CSV feedback research runs.

    Purpose:
    - local feedback accountability
    - scalable traceability
    - source-level tracking
    - future weekly/monthly intelligence reporting

    Security rules:
    - Registry must stay inside reports/intelligence.
    - Registry must be JSON.
    - Source/report paths are recorded only, not executed.
    """

    DEFAULT_REGISTRY_PATH = Path("reports/intelligence/local_feedback_run_index.json")

    def __init__(self, registry_path: str | Path = DEFAULT_REGISTRY_PATH):
        self.registry_path = self._validate_registry_path(Path(registry_path))
        self.registry_path.parent.mkdir(parents=True, exist_ok=True)

    def add_run(
        self,
        *,
        run_result: LocalFeedbackResearchRunResult,
        local_feedback_report_path: str,
    ) -> Path:
        registry = self._load_registry()

        entry = LocalFeedbackRegistryEntry(
            run_id=str(uuid.uuid4()),
            source_path=run_result.source_path,
            industry=run_result.industry,
            source_type=run_result.source_type,
            loaded_count=run_result.loaded_count,
            processed_count=run_result.processed_count,
            successful_count=run_result.successful_count,
            blocked_count=run_result.blocked_count,
            local_feedback_report_path=local_feedback_report_path,
        )

        updated_registry = LocalFeedbackRunRegistry(
            runs=[*registry.runs, entry]
        )

        self.registry_path.write_text(
            json.dumps(self._to_json(updated_registry), indent=2, sort_keys=True),
            encoding="utf-8",
        )

        return self.registry_path

    def _load_registry(self) -> LocalFeedbackRunRegistry:
        if not self.registry_path.exists():
            return LocalFeedbackRunRegistry()

        raw_data = json.loads(self.registry_path.read_text(encoding="utf-8"))

        runs = [
            LocalFeedbackRegistryEntry(**item)
            for item in raw_data.get("runs", [])
        ]

        return LocalFeedbackRunRegistry(runs=runs)

    def _to_json(self, registry: LocalFeedbackRunRegistry) -> dict[str, Any]:
        return {
            "runs": [
                asdict(run)
                for run in registry.runs
            ]
        }

    def _validate_registry_path(self, registry_path: Path) -> Path:
        resolved = registry_path.resolve()
        project_root = Path.cwd().resolve()
        allowed_root = (project_root / "reports" / "intelligence").resolve()

        if not str(resolved).startswith(str(allowed_root)):
            raise LocalFeedbackRegistryError(
                "Local feedback registry must stay inside reports/intelligence"
            )

        if resolved.suffix != ".json":
            raise LocalFeedbackRegistryError(
                "Local feedback registry must be a JSON file"
            )

        return resolved
