import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from src.research.planned_reddit_research_runner import PlannedRedditResearchBatchResult


class BatchRegistryError(Exception):
    pass


@dataclass(frozen=True)
class BatchRegistryEntry:
    batch_id: str
    industry: str
    planned_count: int
    successful_count: int
    blocked_count: int
    batch_report_path: str
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())


@dataclass(frozen=True)
class BatchRunRegistry:
    batches: list[BatchRegistryEntry] = field(default_factory=list)


class BatchRunRegistryWriter:
    """
    Maintains a central index of planned research batch runs.

    Purpose:
    - batch-level accountability
    - scalable traceability
    - easier weekly/monthly intelligence reporting

    Security rules:
    - Registry must stay inside reports/intelligence.
    - Registry must be JSON.
    - Batch report paths are recorded only, not executed.
    """

    DEFAULT_REGISTRY_PATH = Path("reports/intelligence/batch_run_index.json")

    def __init__(self, registry_path: str | Path = DEFAULT_REGISTRY_PATH):
        self.registry_path = self._validate_registry_path(Path(registry_path))
        self.registry_path.parent.mkdir(parents=True, exist_ok=True)

    def add_batch(
        self,
        *,
        batch_result: PlannedRedditResearchBatchResult,
        batch_report_path: str,
    ) -> Path:
        registry = self._load_registry()

        entry = BatchRegistryEntry(
            batch_id=str(uuid.uuid4()),
            industry=batch_result.industry,
            planned_count=batch_result.planned_count,
            successful_count=batch_result.successful_count,
            blocked_count=batch_result.blocked_count,
            batch_report_path=batch_report_path,
        )

        updated_registry = BatchRunRegistry(
            batches=[*registry.batches, entry]
        )

        self.registry_path.write_text(
            json.dumps(self._to_json(updated_registry), indent=2, sort_keys=True),
            encoding="utf-8",
        )

        return self.registry_path

    def _load_registry(self) -> BatchRunRegistry:
        if not self.registry_path.exists():
            return BatchRunRegistry()

        raw_data = json.loads(self.registry_path.read_text(encoding="utf-8"))

        batches = [
            BatchRegistryEntry(**item)
            for item in raw_data.get("batches", [])
        ]

        return BatchRunRegistry(batches=batches)

    def _to_json(self, registry: BatchRunRegistry) -> dict[str, Any]:
        return {
            "batches": [
                asdict(batch)
                for batch in registry.batches
            ]
        }

    def _validate_registry_path(self, registry_path: Path) -> Path:
        resolved = registry_path.resolve()
        project_root = Path.cwd().resolve()
        allowed_root = (project_root / "reports" / "intelligence").resolve()

        if not str(resolved).startswith(str(allowed_root)):
            raise BatchRegistryError(
                "Batch registry must stay inside reports/intelligence"
            )

        if resolved.suffix != ".json":
            raise BatchRegistryError("Batch registry must be a JSON file")

        return resolved
