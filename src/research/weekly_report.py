import json
from collections import Counter
from pathlib import Path
from typing import Any


class WeeklyIntelligenceReportError(Exception):
    pass


class WeeklyIntelligenceReportGenerator:
    """
    Generates a weekly Markdown intelligence report from research registries.

    Inputs:
    - reports/intelligence/research_run_index.json
    - reports/intelligence/batch_run_index.json

    Security rules:
    - Registry paths must stay inside reports/intelligence.
    - Weekly report must be written inside reports/weekly.
    - No user-provided arbitrary output paths.
    - Report content is generated from recorded registries only.
    """

    DEFAULT_REGISTRY_PATH = Path("reports/intelligence/research_run_index.json")
    DEFAULT_BATCH_REGISTRY_PATH = Path("reports/intelligence/batch_run_index.json")
    DEFAULT_OUTPUT_DIR = Path("reports/weekly")

    def __init__(
        self,
        registry_path: str | Path = DEFAULT_REGISTRY_PATH,
        batch_registry_path: str | Path = DEFAULT_BATCH_REGISTRY_PATH,
        output_dir: str | Path = DEFAULT_OUTPUT_DIR,
    ):
        self.registry_path = self._validate_registry_path(Path(registry_path))
        self.batch_registry_path = self._validate_registry_path(Path(batch_registry_path))
        self.output_dir = self._validate_output_dir(Path(output_dir))
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def generate(self) -> Path:
        registry = self._load_json(self.registry_path, default_key="runs")
        batch_registry = self._load_json(self.batch_registry_path, default_key="batches")

        runs = registry.get("runs", [])
        batches = batch_registry.get("batches", [])

        report_path = self._safe_report_path()
        content = self._build_report(runs=runs, batches=batches)

        report_path.write_text(content, encoding="utf-8")

        return report_path

    def _load_json(self, path: Path, default_key: str) -> dict[str, Any]:
        if not path.exists():
            return {default_key: []}

        return json.loads(path.read_text(encoding="utf-8"))

    def _build_report(
        self,
        *,
        runs: list[dict[str, Any]],
        batches: list[dict[str, Any]],
    ) -> str:
        total_runs = len(runs)
        successful_runs = sum(1 for run in runs if run.get("status") == "success")
        blocked_runs = sum(1 for run in runs if run.get("status") == "blocked")

        accepted_total = sum(int(run.get("accepted_count", 0)) for run in runs)
        rejected_total = sum(int(run.get("rejected_count", 0)) for run in runs)
        processed_total = sum(int(run.get("processed_count", 0)) for run in runs)

        industries = Counter(run.get("industry", "unknown") for run in runs)
        subreddits = Counter(run.get("subreddit", "unknown") for run in runs)
        queries = Counter(run.get("query", "unknown") for run in runs)

        report_paths: list[str] = []
        hermes_memory_paths: list[str] = []

        for run in runs:
            report_paths.extend(run.get("report_paths", []))
            hermes_memory_paths.extend(run.get("hermes_memory_paths", []))

        latest_runs = runs[-5:]

        total_batches = len(batches)
        total_planned_batch_jobs = sum(
            int(batch.get("planned_count", 0))
            for batch in batches
        )
        total_successful_batch_jobs = sum(
            int(batch.get("successful_count", 0))
            for batch in batches
        )
        total_blocked_batch_jobs = sum(
            int(batch.get("blocked_count", 0))
            for batch in batches
        )

        batch_industries = Counter(
            batch.get("industry", "unknown")
            for batch in batches
        )

        batch_report_paths = [
            batch.get("batch_report_path", "")
            for batch in batches
            if batch.get("batch_report_path")
        ]

        latest_batches = batches[-5:]

        content = f"""# Weekly Research Intelligence Report

## Summary

- Total Research Runs: {total_runs}
- Successful Runs: {successful_runs}
- Blocked Runs: {blocked_runs}
- Processed Posts: {processed_total}
- Accepted Opportunities: {accepted_total}
- Rejected Posts: {rejected_total}

## Batch Research Summary

- Total Batch Runs: {total_batches}
- Total Planned Batch Jobs: {total_planned_batch_jobs}
- Successful Batch Jobs: {total_successful_batch_jobs}
- Blocked Batch Jobs: {total_blocked_batch_jobs}

## Top Industries

{self._format_counter(industries)}

## Top Batch Industries

{self._format_counter(batch_industries)}

## Top Subreddits

{self._format_counter(subreddits)}

## Top Queries

{self._format_counter(queries)}

## Generated Opportunity Reports

{self._format_list(report_paths, "- No reports generated yet.")}

## Hermes Memory Records

{self._format_list(hermes_memory_paths, "- No Hermes memory records generated yet.")}

## Batch Reports

{self._format_list(batch_report_paths, "- No batch reports generated yet.")}

## Latest Research Runs

{self._format_latest_runs(latest_runs)}

## Latest Batch Runs

{self._format_latest_batches(latest_batches)}

## Recommended Next Actions

{self._recommended_actions(
    accepted_total=accepted_total,
    total_runs=total_runs,
    total_batches=total_batches,
    total_blocked_batch_jobs=total_blocked_batch_jobs,
)}
"""

        return content

    def _format_counter(self, counter: Counter[str]) -> str:
        if not counter:
            return "- No data yet."

        return "\n".join(
            f"- {name}: {count}"
            for name, count in counter.most_common(5)
        )

    def _format_list(self, values: list[str], fallback: str) -> str:
        if not values:
            return fallback

        unique_values = list(dict.fromkeys(values))

        return "\n".join(f"- {value}" for value in unique_values[:25])

    def _format_latest_runs(self, runs: list[dict[str, Any]]) -> str:
        if not runs:
            return "- No research runs recorded yet."

        lines = []

        for run in runs:
            lines.append(
                "- "
                f"{run.get('timestamp', 'unknown time')} | "
                f"{run.get('status', 'unknown')} | "
                f"{run.get('subreddit', 'unknown')} | "
                f"{run.get('query', 'unknown')} | "
                f"accepted: {run.get('accepted_count', 0)}"
            )

        return "\n".join(lines)

    def _format_latest_batches(self, batches: list[dict[str, Any]]) -> str:
        if not batches:
            return "- No batch runs recorded yet."

        lines = []

        for batch in batches:
            lines.append(
                "- "
                f"{batch.get('timestamp', 'unknown time')} | "
                f"{batch.get('industry', 'unknown')} | "
                f"planned: {batch.get('planned_count', 0)} | "
                f"success: {batch.get('successful_count', 0)} | "
                f"blocked: {batch.get('blocked_count', 0)}"
            )

        return "\n".join(lines)

    def _recommended_actions(
        self,
        *,
        accepted_total: int,
        total_runs: int,
        total_batches: int,
        total_blocked_batch_jobs: int,
    ) -> str:
        if total_runs == 0 and total_batches == 0:
            return "- Run the first controlled research job or planned batch."

        actions = [
            "- Review generated opportunity reports.",
            "- Compare repeated pain points across jobs and batches.",
            "- Validate high-scoring opportunities with additional sources.",
            "- Do not move to MVP planning until strategic validation is reviewed.",
        ]

        if accepted_total == 0:
            actions.append("- Review research queries and improve pain extraction keywords.")

        if total_blocked_batch_jobs > 0:
            actions.append("- Review blocked batch jobs before expanding automation.")

        return "\n".join(actions)

    def _validate_registry_path(self, registry_path: Path) -> Path:
        resolved = registry_path.resolve()
        project_root = Path.cwd().resolve()
        allowed_root = (project_root / "reports" / "intelligence").resolve()

        if not str(resolved).startswith(str(allowed_root)):
            raise WeeklyIntelligenceReportError(
                "Registry path must stay inside reports/intelligence"
            )

        if resolved.suffix != ".json":
            raise WeeklyIntelligenceReportError("Registry must be a JSON file")

        return resolved

    def _validate_output_dir(self, output_dir: Path) -> Path:
        resolved = output_dir.resolve()
        project_root = Path.cwd().resolve()
        allowed_root = (project_root / "reports" / "weekly").resolve()

        if not str(resolved).startswith(str(allowed_root)):
            raise WeeklyIntelligenceReportError(
                "Weekly report output must stay inside reports/weekly"
            )

        return resolved

    def _safe_report_path(self) -> Path:
        report_path = (self.output_dir / "weekly_intelligence_report.md").resolve()

        if not str(report_path).startswith(str(self.output_dir)):
            raise WeeklyIntelligenceReportError("Unsafe weekly report path detected")

        return report_path
