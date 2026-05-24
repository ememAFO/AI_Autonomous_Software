import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path


class RunManifestError(Exception):
    pass


@dataclass(frozen=True)
class ResearchRunManifest:
    run_id: str
    status: str
    query: str
    subreddit: str
    industry: str
    final_workflow_stage: str
    processed_count: int
    accepted_count: int
    rejected_count: int
    report_paths: list[str]
    hermes_memory_count: int = 0
    hermes_memory_paths: list[str] = field(default_factory=list)
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())


class ResearchRunManifestWriter:
    """
    Writes one JSON manifest per research run.

    Security rules:
    - Manifest files must stay inside reports/intelligence/runs.
    - File names are generated internally.
    - No user-provided file paths.
    - Path traversal is blocked.
    """

    DEFAULT_OUTPUT_DIR = Path("reports/intelligence/runs")

    def __init__(self, output_dir: str | Path = DEFAULT_OUTPUT_DIR):
        self.output_dir = self._validate_output_dir(Path(output_dir))
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def create_manifest(
        self,
        *,
        status: str,
        query: str,
        subreddit: str,
        industry: str,
        final_workflow_stage: str,
        processed_count: int,
        accepted_count: int,
        rejected_count: int,
        report_paths: list[str],
        hermes_memory_count: int = 0,
        hermes_memory_paths: list[str] | None = None,
    ) -> ResearchRunManifest:
        run_id = str(uuid.uuid4())

        return ResearchRunManifest(
            run_id=run_id,
            status=status,
            query=query,
            subreddit=subreddit,
            industry=industry,
            final_workflow_stage=final_workflow_stage,
            processed_count=processed_count,
            accepted_count=accepted_count,
            rejected_count=rejected_count,
            report_paths=report_paths,
            hermes_memory_count=hermes_memory_count,
            hermes_memory_paths=hermes_memory_paths or [],
        )

    def write(self, manifest: ResearchRunManifest) -> Path:
        manifest_path = self._safe_manifest_path(manifest)

        manifest_path.write_text(
            json.dumps(asdict(manifest), indent=2, sort_keys=True),
            encoding="utf-8",
        )

        return manifest_path

    def _validate_output_dir(self, output_dir: Path) -> Path:
        resolved = output_dir.resolve()
        project_root = Path.cwd().resolve()
        allowed_root = (project_root / "reports" / "intelligence" / "runs").resolve()

        if not str(resolved).startswith(str(allowed_root)):
            raise RunManifestError(
                "Run manifest directory must stay inside reports/intelligence/runs"
            )

        return resolved

    def _safe_manifest_path(self, manifest: ResearchRunManifest) -> Path:
        safe_query = self._safe_filename(manifest.query)
        safe_subreddit = self._safe_filename(manifest.subreddit)

        filename = f"{manifest.timestamp[:10]}_{safe_subreddit}_{safe_query}_{manifest.run_id}.json"
        manifest_path = (self.output_dir / filename).resolve()

        if not str(manifest_path).startswith(str(self.output_dir)):
            raise RunManifestError("Unsafe manifest path detected")

        return manifest_path

    def _safe_filename(self, value: str) -> str:
        safe = value.lower().strip().replace(" ", "-")
        safe = "".join(char for char in safe if char.isalnum() or char in {"-", "_"})
        return safe[:80] or "research-run"
