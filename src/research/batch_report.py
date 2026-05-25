from datetime import UTC, datetime
from pathlib import Path

from src.research.planned_reddit_research_runner import PlannedRedditResearchBatchResult


class BatchReportError(Exception):
    pass


class PlannedRedditBatchReportGenerator:
    """
    Generates a Markdown report for one planned Reddit research batch.

    Purpose:
    - accountability
    - traceability
    - scalable batch review
    - proof that the batch followed the controlled research cycle

    Security rules:
    - Batch reports must stay inside reports/intelligence/batches.
    - File names are generated internally.
    - Path traversal is blocked.
    """

    DEFAULT_OUTPUT_DIR = Path("reports/intelligence/batches")

    def __init__(self, output_dir: str | Path = DEFAULT_OUTPUT_DIR):
        self.output_dir = self._validate_output_dir(Path(output_dir))
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def generate(self, batch_result: PlannedRedditResearchBatchResult) -> Path:
        report_path = self._safe_report_path(batch_result.industry)
        content = self._build_report(batch_result)
        report_path.write_text(content, encoding="utf-8")
        return report_path

    def _build_report(self, batch_result: PlannedRedditResearchBatchResult) -> str:
        generated_at = datetime.now(UTC).isoformat()

        job_lines = []
        report_paths: list[str] = []
        manifest_paths: list[str] = []
        hermes_memory_paths: list[str] = []
        blocked_errors: list[str] = []

        for index, result in enumerate(batch_result.results, start=1):
            job_lines.append(
                "- "
                f"Job {index}: {result.status.upper()} | "
                f"subreddit={result.planned_job.query.subreddit} | "
                f"query={result.planned_job.query.query} | "
                f"processed={result.processed_count} | "
                f"accepted={result.accepted_count} | "
                f"rejected={result.rejected_count} | "
                f"stage={result.final_workflow_stage or 'N/A'}"
            )

            report_paths.extend(result.report_paths)

            if result.manifest_path:
                manifest_paths.append(result.manifest_path)

            hermes_memory_paths.extend(result.hermes_memory_paths)

            if result.error:
                blocked_errors.append(
                    f"{result.planned_job.query.subreddit} | "
                    f"{result.planned_job.query.query}: {result.error}"
                )

        content = f"""# Planned Reddit Research Batch Report

## Batch Summary

- Industry: {batch_result.industry}
- Generated At: {generated_at}
- Planned Jobs: {batch_result.planned_count}
- Successful Jobs: {batch_result.successful_count}
- Blocked Jobs: {batch_result.blocked_count}

## Workflow Cycle

Each successful job followed:

RESEARCH PLANNING
→ DISCOVER
→ FETCH
→ EXTRACT
→ CLEAN
→ ANALYZE
→ SCORE
→ REPORT
→ MANIFEST
→ REGISTRY
→ HERMES MEMORY
→ AUDIT LOG

## Job Results

{self._format_list(job_lines, "- No jobs recorded.")}

## Generated Opportunity Reports

{self._format_list(self._dedupe(report_paths), "- No opportunity reports generated.")}

## Run Manifests

{self._format_list(self._dedupe(manifest_paths), "- No run manifests generated.")}

## Hermes Memory Records

{self._format_list(self._dedupe(hermes_memory_paths), "- No Hermes memory records generated.")}

## Blocked Job Errors

{self._format_list(blocked_errors, "- No blocked job errors.")}

## Accountability Notes

- This batch report summarizes one complete planned research batch.
- Individual job manifests provide per-run traceability.
- The research run registry provides cross-run indexing.
- Audit logs provide event-level accountability.
- Hermes memory records preserve structured intelligence for later trend analysis.

## Recommended Next Actions

{self._recommended_actions(batch_result)}
"""

        return content

    def _recommended_actions(self, batch_result: PlannedRedditResearchBatchResult) -> str:
        if batch_result.successful_count == 0:
            return "- Review planner configuration and source policy before running more batches."

        if batch_result.blocked_count > 0:
            return "- Review blocked job errors before expanding this batch."

        return "\n".join(
            [
                "- Review generated opportunity reports.",
                "- Compare repeated pain points across jobs.",
                "- Validate high-scoring opportunities with additional sources.",
                "- Do not move to MVP planning until strategic validation is reviewed.",
            ]
        )

    def _format_list(self, values: list[str], fallback: str) -> str:
        if not values:
            return fallback

        return "\n".join(f"- {value}" if not value.startswith("- ") else value for value in values)

    def _dedupe(self, values: list[str]) -> list[str]:
        return list(dict.fromkeys(values))

    def _validate_output_dir(self, output_dir: Path) -> Path:
        resolved = output_dir.resolve()
        project_root = Path.cwd().resolve()
        allowed_root = (project_root / "reports" / "intelligence" / "batches").resolve()

        if not str(resolved).startswith(str(allowed_root)):
            raise BatchReportError(
                "Batch report output directory must stay inside reports/intelligence/batches"
            )

        return resolved

    def _safe_report_path(self, industry: str) -> Path:
        safe_industry = self._safe_filename(industry)
        timestamp = datetime.now(UTC).strftime("%Y-%m-%d_%H-%M-%S")
        report_path = (self.output_dir / f"{timestamp}_{safe_industry}_batch_report.md").resolve()

        if not str(report_path).startswith(str(self.output_dir)):
            raise BatchReportError("Unsafe batch report path detected")

        return report_path

    def _safe_filename(self, value: str) -> str:
        safe = value.lower().strip().replace(" ", "-")
        safe = "".join(char for char in safe if char.isalnum() or char in {"-", "_"})
        return safe[:80] or "batch"
