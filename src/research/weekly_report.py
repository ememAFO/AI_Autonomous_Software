import json
from collections import Counter
from pathlib import Path
from typing import Any


class WeeklyIntelligenceReportError(Exception):
    pass


class WeeklyIntelligenceReportGenerator:
    """
    Generates a weekly Markdown intelligence report from the research run registry.

    Security rules:
    - Registry must be read from reports/intelligence.
    - Weekly report must be written inside reports/weekly.
    - No user-provided arbitrary output paths.
    - Report content is generated from recorded manifests/registry only.
    """

    DEFAULT_REGISTRY_PATH = Path("reports/intelligence/research_run_index.json")
    DEFAULT_OUTPUT_DIR = Path("reports/weekly")

    def __init__(
        self,
        registry_path: str | Path = DEFAULT_REGISTRY_PATH,
        output_dir: str | Path = DEFAULT_OUTPUT_DIR,
    ):
        self.registry_path = self._validate_registry_path(Path(registry_path))
        self.output_dir = self._validate_output_dir(Path(output_dir))
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def generate(self) -> Path:
        registry = self._load_registry()
        runs = registry.get("runs", [])

        report_path = self._safe_report_path()

        content = self._build_report(runs)

        report_path.write_text(content, encoding="utf-8")

        return report_path

    def _load_registry(self) -> dict[str, Any]:
        if not self.registry_path.exists():
            return {"runs": []}

        return json.loads(self.registry_path.read_text(encoding="utf-8"))

    def _build_report(self, runs: list[dict[str, Any]]) -> str:
        total_runs = len(runs)
        successful_runs = sum(1 for run in runs if run.get("status") == "success")
        blocked_runs = sum(1 for run in runs if run.get("status") == "blocked")

        accepted_total = sum(int(run.get("accepted_count", 0)) for run in runs)
        rejected_total = sum(int(run.get("rejected_count", 0)) for run in runs)
        processed_total = sum(int(run.get("processed_count", 0)) for run in runs)

        industries = Counter(run.get("industry", "unknown") for run in runs)
        subreddits = Counter(run.get("subreddit", "unknown") for run in runs)
        queries = Counter(run.get("query", "unknown") for run in runs)

        report_paths = []
        for run in runs:
            report_paths.extend(run.get("report_paths", []))

        latest_runs = runs[-5:]

        content = f"""# Weekly Research Intelligence Report

## Summary

- Total Research Runs: {total_runs}
- Successful Runs: {successful_runs}
- Blocked Runs: {blocked_runs}
- Processed Posts: {processed_total}
- Accepted Opportunities: {accepted_total}
- Rejected Posts: {rejected_total}

## Top Industries

{self._format_counter(industries)}

## Top Subreddits

{self._format_counter(subreddits)}

## Top Queries

{self._format_counter(queries)}

## Generated Opportunity Reports

{self._format_list(report_paths)}

## Latest Research Runs

{self._format_latest_runs(latest_runs)}

## Recommended Next Actions

{self._recommended_actions(accepted_total, total_runs)}
"""

        return content

    def _format_counter(self, counter: Counter[str]) -> str:
        if not counter:
            return "- No data yet."

        return "\n".join(
            f"- {name}: {count}"
            for name, count in counter.most_common(5)
        )

    def _format_list(self, values: list[str]) -> str:
        if not values:
            return "- No reports generated yet."

        unique_values = list(dict.fromkeys(values))

        return "\n".join(f"- {value}" for value in unique_values[:20])

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

    def _recommended_actions(self, accepted_total: int, total_runs: int) -> str:
        if total_runs == 0:
            return "- Run the first controlled research job."

        if accepted_total == 0:
            return "- Review research queries and improve pain extraction keywords."

        return "\n".join(
            [
                "- Review the generated opportunity reports.",
                "- Validate repeated pain points with more sources.",
                "- Prioritize opportunities with strong urgency, monetization, and automation potential.",
            ]
        )

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
