import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from src.research.run_manifest import ResearchRunManifest


class ResearchRunRegistryError(Exception):
    pass


@dataclass(frozen=True)
class ResearchRunRegistryEntry:
    run_id: str
    status: str
    query: str
    subreddit: str
    industry: str
    final_workflow_stage: str
    processed_count: int
    accepted_count: int
    rejected_count: int
    manifest_path: str
    report_paths: list[str]
    timestamp: str


@dataclass(frozen=True)
class ResearchRunRegistry:
    runs: list[ResearchRunRegistryEntry] = field(default_factory=list)


class ResearchRunRegistryWriter:
    """
    Maintains a central index of all research runs.

    Security rules:
    - Registry must stay inside reports/intelligence.
    - Registry file must be JSON.
    - Manifest paths are recorded, not executed.
    - Report paths are recorded, not executed.
    """

    DEFAULT_REGISTRY_PATH = Path("reports/intelligence/research_run_index.json")

    def __init__(self, registry_path: str | Path = DEFAULT_REGISTRY_PATH):
        self.registry_path = self._validate_registry_path(Path(registry_path))
        self.registry_path.parent.mkdir(parents=True, exist_ok=True)

    def add_run(
        self,
        *,
        manifest: ResearchRunManifest,
        manifest_path: str,
    ) -> Path:
        registry = self._load_registry()

        entry = ResearchRunRegistryEntry(
            run_id=manifest.run_id,
            status=manifest.status,
            query=manifest.query,
            subreddit=manifest.subreddit,
            industry=manifest.industry,
            final_workflow_stage=manifest.final_workflow_stage,
            processed_count=manifest.processed_count,
            accepted_count=manifest.accepted_count,
            rejected_count=manifest.rejected_count,
            manifest_path=manifest_path,
            report_paths=manifest.report_paths,
            timestamp=manifest.timestamp,
        )

        updated_registry = ResearchRunRegistry(
            runs=[*registry.runs, entry]
        )

        self.registry_path.write_text(
            json.dumps(self._to_json(updated_registry), indent=2, sort_keys=True),
            encoding="utf-8",
        )

        return self.registry_path

    def _load_registry(self) -> ResearchRunRegistry:
        if not self.registry_path.exists():
            return ResearchRunRegistry()

        raw_data = json.loads(self.registry_path.read_text(encoding="utf-8"))

        runs = [
            ResearchRunRegistryEntry(**item)
            for item in raw_data.get("runs", [])
        ]

        return ResearchRunRegistry(runs=runs)

    def _to_json(self, registry: ResearchRunRegistry) -> dict[str, Any]:
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
            raise ResearchRunRegistryError(
                "Research run registry must stay inside reports/intelligence"
            )

        if resolved.suffix != ".json":
            raise ResearchRunRegistryError(
                "Research run registry must be a JSON file"
            )

        return resolved
