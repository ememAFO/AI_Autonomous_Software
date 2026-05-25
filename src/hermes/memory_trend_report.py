from datetime import UTC, datetime
from pathlib import Path

from src.hermes.memory_trend_detector import MemoryTrendSummary


class MemoryTrendReportError(Exception):
    pass


class HermesMemoryTrendReportGenerator:
    """
    Generates a Markdown product-intelligence report from Hermes memory trends.

    Security rules:
    - Writes only inside reports/intelligence
    - Does not execute memory content
    - Produces a readable summary for human review
    """

    DEFAULT_OUTPUT_DIR = Path("reports/intelligence")

    def __init__(self, output_dir: str | Path = DEFAULT_OUTPUT_DIR):
        self.output_dir = self._validate_output_dir(Path(output_dir))
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def generate(self, summary: MemoryTrendSummary) -> Path:
        report_path = self._safe_report_path()
        content = self._build_report(summary)
        report_path.write_text(content, encoding="utf-8")
        return report_path

    def _build_report(self, summary: MemoryTrendSummary) -> str:
        generated_at = datetime.now(UTC).isoformat()

        content = f"""# Hermes Memory Trend Report

## Summary

- Generated At: {generated_at}
- Total Memory Records: {summary.total_records}
- High-Confidence Records: {len(summary.high_confidence_records)}

## Top Industries

{self._format_pairs(summary.top_industries, "- No industries found.")}

## Top Recommendations

{self._format_pairs(summary.top_recommendations, "- No recommendations found.")}

## Repeated Pain Terms

{self._format_pairs(summary.repeated_pain_terms, "- No repeated pain terms found.")}

## High-Confidence Opportunities

{self._format_high_confidence(summary)}

## Recommended Next Actions

{self._recommended_actions(summary)}
"""

        return content

    def _format_pairs(self, values: list[tuple[str, int]], fallback: str) -> str:
        if not values:
            return fallback

        return "\n".join(f"- {name}: {count}" for name, count in values)

    def _format_high_confidence(self, summary: MemoryTrendSummary) -> str:
        if not summary.high_confidence_records:
            return "- No high-confidence records yet."

        lines = []

        for record in summary.high_confidence_records[:10]:
            lines.append(
                "- "
                f"{record.industry} | "
                f"{record.recommendation} | "
                f"score={record.score} | "
                f"{record.pain_point[:120]}"
            )

        return "\n".join(lines)

    def _recommended_actions(self, summary: MemoryTrendSummary) -> str:
        if summary.total_records == 0:
            return "- Run research jobs to create Hermes memory records."

        if not summary.high_confidence_records:
            return "- Collect more evidence before moving opportunities toward validation."

        return "\n".join(
            [
                "- Review high-confidence opportunities.",
                "- Compare repeated pain terms against opportunity reports.",
                "- Validate strongest opportunities with additional non-Reddit sources.",
                "- Do not move to MVP planning until strategic validation and evidence are reviewed.",
            ]
        )

    def _validate_output_dir(self, output_dir: Path) -> Path:
        resolved = output_dir.resolve()
        project_root = Path.cwd().resolve()
        allowed_root = (project_root / "reports" / "intelligence").resolve()

        if not str(resolved).startswith(str(allowed_root)):
            raise MemoryTrendReportError(
                "Memory trend report must stay inside reports/intelligence"
            )

        return resolved

    def _safe_report_path(self) -> Path:
        report_path = (self.output_dir / "hermes_memory_trend_report.md").resolve()

        if not str(report_path).startswith(str(self.output_dir)):
            raise MemoryTrendReportError("Unsafe Hermes memory trend report path detected")

        return report_path
