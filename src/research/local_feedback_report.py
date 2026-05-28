from datetime import UTC, datetime
from pathlib import Path

from src.research.local_feedback_research_runner import LocalFeedbackResearchRunResult
from src.utils.path_normalizer import ProjectPathNormalizer, PathNormalizerError


class LocalFeedbackReportError(Exception):
    pass


class LocalFeedbackReportGenerator:
    """
    Generates a Markdown report for one local CSV feedback research run.

    Purpose:
    - accountability
    - traceability
    - review of accepted and blocked feedback rows
    - proof that local dataset processing followed the controlled research cycle

    Security rules:
    - Reports must stay inside reports/intelligence/local_feedback.
    - File names are generated internally.
    - Path traversal is blocked.
    """

    DEFAULT_OUTPUT_DIR = Path("reports/intelligence/local_feedback")

    def __init__(self, output_dir: str | Path = DEFAULT_OUTPUT_DIR):
        self.output_dir = self._validate_output_dir(Path(output_dir))
        self.path_normalizer = ProjectPathNormalizer()
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def generate(self, run_result: LocalFeedbackResearchRunResult) -> Path:
        report_path = self._safe_report_path(run_result)
        content = self._build_report(run_result)
        report_path.write_text(content, encoding="utf-8")
        return report_path

    def _build_report(self, run_result: LocalFeedbackResearchRunResult) -> str:
        generated_at = datetime.now(UTC).isoformat()

        successful_reports = []
        manifest_paths = []
        registry_paths = []
        hermes_memory_paths = []
        blocked_errors = []

        for index, item_result in enumerate(run_result.results, start=1):
            if item_result.report_path:
                successful_reports.append(item_result.report_path)

            if item_result.manifest_path:
                manifest_paths.append(item_result.manifest_path)

            if item_result.registry_path:
                registry_paths.append(item_result.registry_path)

            if item_result.hermes_memory_path:
                hermes_memory_paths.append(item_result.hermes_memory_path)

            if item_result.error:
                blocked_errors.append(
                    f"Row {index}: {item_result.error}"
                )

        item_lines = []

        for index, item_result in enumerate(run_result.results, start=1):
            item_lines.append(
                "- "
                f"Row {index}: {item_result.status.upper()} | "
                f"report={self._normalize_path(item_result.report_path) if item_result.report_path else 'N/A'} | "
                f"manifest={self._normalize_path(item_result.manifest_path) if item_result.manifest_path else 'N/A'}"
            )

        content = f"""# Local Feedback Research Report

## Run Summary

- Generated At: {generated_at}
- Source Path: {self._normalize_path(run_result.source_path)}
- Industry: {run_result.industry}
- Source Type: {run_result.source_type}
- Loaded Rows: {run_result.loaded_count}
- Processed Rows: {run_result.processed_count}
- Successful Rows: {run_result.successful_count}
- Blocked Rows: {run_result.blocked_count}

## Workflow Cycle

Each successful row followed:

LOCAL CSV LOAD
→ FEEDBACK CLEANING
→ PAIN EXTRACTION
→ PAIN REASONING FALLBACK IF NEEDED
→ STRATEGIC VALIDATION
→ SCORING
→ OPPORTUNITY REPORT
→ MANIFEST
→ REGISTRY
→ HERMES MEMORY
→ AUDIT LOG

## Item Results

{self._format_list(item_lines, "- No item results recorded.")}

## Generated Opportunity Reports

{self._format_list(self._normalize_many(successful_reports), "- No opportunity reports generated.")}

## Run Manifests

{self._format_list(self._normalize_many(manifest_paths), "- No run manifests generated.")}

## Registry Paths

{self._format_list(self._normalize_many(registry_paths), "- No registry paths recorded.")}

## Hermes Memory Records

{self._format_list(self._normalize_many(hermes_memory_paths), "- No Hermes memory records generated.")}

## Blocked Row Errors

{self._format_list(blocked_errors, "- No blocked rows.")}

## Accountability Notes

- This report summarizes one local CSV feedback research run.
- Individual run manifests provide per-row traceability.
- The research run registry provides cross-run indexing.
- Hermes memory records preserve structured intelligence for trend analysis.
- Blocked rows prove the system is not forcing weak feedback into false opportunities.

## Recommended Next Actions

{self._recommended_actions(run_result)}
"""

        return content

    def _recommended_actions(self, run_result: LocalFeedbackResearchRunResult) -> str:
        if run_result.successful_count == 0:
            return "\n".join(
                [
                    "- Review extracted complaint text before expanding processing.",
                    "- Check whether the dataset contains weak, positive, or non-business feedback.",
                    "- Do not lower pain standards just to increase accepted rows.",
                ]
            )

        if run_result.blocked_count > 0:
            return "\n".join(
                [
                    "- Review successful opportunity reports.",
                    "- Review blocked rows to identify false negatives.",
                    "- Improve pain reasoning only if blocked rows contain clear business pain.",
                    "- Validate accepted pain themes with additional sources before MVP planning.",
                ]
            )

        return "\n".join(
            [
                "- Review generated opportunity reports.",
                "- Compare accepted rows for repeated pain themes.",
                "- Validate strongest themes with another dataset/source.",
                "- Do not move to MVP planning until strategic validation is reviewed.",
            ]
        )

    def _format_list(self, values: list[str], fallback: str) -> str:
        if not values:
            return fallback

        unique_values = list(dict.fromkeys(values))

        return "\n".join(f"- {value}" for value in unique_values)

    def _normalize_many(self, values: list[str]) -> list[str]:
        return [self._normalize_path(value) for value in values]

    def _normalize_path(self, path: str) -> str:
        try:
            return self.path_normalizer.normalize(path)
        except PathNormalizerError:
            return "[blocked unsafe path]"

    def _validate_output_dir(self, output_dir: Path) -> Path:
        resolved = output_dir.resolve()
        project_root = Path.cwd().resolve()
        allowed_root = (
            project_root / "reports" / "intelligence" / "local_feedback"
        ).resolve()

        if not str(resolved).startswith(str(allowed_root)):
            raise LocalFeedbackReportError(
                "Local feedback report output must stay inside reports/intelligence/local_feedback"
            )

        return resolved

    def _safe_report_path(self, run_result: LocalFeedbackResearchRunResult) -> Path:
        timestamp = datetime.now(UTC).strftime("%Y-%m-%d_%H-%M-%S")
        industry = self._safe_filename(run_result.industry)
        source_type = self._safe_filename(run_result.source_type)

        report_path = (
            self.output_dir / f"{timestamp}_{industry}_{source_type}_feedback_report.md"
        ).resolve()

        if not str(report_path).startswith(str(self.output_dir)):
            raise LocalFeedbackReportError("Unsafe local feedback report path detected")

        return report_path

    def _safe_filename(self, value: str) -> str:
        safe = value.lower().strip().replace(" ", "-")
        safe = "".join(char for char in safe if char.isalnum() or char in {"-", "_"})
        return safe[:80] or "local-feedback"
