from datetime import UTC, datetime
from pathlib import Path

from src.hermes.memory_trend_detector import MemoryTrendSummary, OpportunityTheme
from src.utils.path_normalizer import ProjectPathNormalizer, PathNormalizerError


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
        self.path_normalizer = ProjectPathNormalizer()
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
- High-Confidence Themes: {len(summary.high_confidence_themes)}

## Top Industries

{self._format_pairs(summary.top_industries, "- No industries found.")}

## Top Recommendations

{self._format_pairs(summary.top_recommendations, "- No recommendations found.")}

## Repeated Pain Terms

{self._format_pairs(summary.repeated_pain_terms, "- No repeated pain terms found.")}

## High-Confidence Opportunity Themes

{self._format_opportunity_themes(summary.high_confidence_themes)}

## Latest High-Confidence Records

{self._format_high_confidence(summary)}

## Recommended Next Actions

{self._recommended_actions(summary)}
"""

        return content

    def _format_pairs(self, values: list[tuple[str, int]], fallback: str) -> str:
        if not values:
            return fallback

        return "\n".join(f"- {name}: {count}" for name, count in values)

    def _format_opportunity_themes(self, themes: list[OpportunityTheme]) -> str:
        if not themes:
            return "- No high-confidence opportunity themes yet."

        blocks: list[str] = []

        for theme in themes[:10]:
            industries = ", ".join(
                f"{industry} ({count})"
                for industry, count in theme.top_industries
            )

            recommendations = ", ".join(
                f"{recommendation} ({count})"
                for recommendation, count in theme.top_recommendations
            )

            report_paths = "\n".join(
                f"  - {self._normalize_path(path)}"
                for path in theme.report_paths[:5]
            ) or "  - No report paths recorded."

            blocks.append(
                "\n".join(
                    [
                        f"### Theme: {theme.theme}",
                        "",
                        f"- Records: {theme.record_count}",
                        f"- Average Score: {theme.average_score}",
                        f"- Top Industries: {industries or 'unknown'}",
                        f"- Top Recommendations: {recommendations or 'unknown'}",
                        f"- Example Pain Point: {theme.example_pain_point[:180]}",
                        "- Related Reports:",
                        report_paths,
                    ]
                )
            )

        return "\n\n".join(blocks)

    def _format_high_confidence(self, summary: MemoryTrendSummary) -> str:
        if not summary.high_confidence_records:
            return "- No high-confidence records yet."

        lines = []

        seen: set[str] = set()

        for record in summary.high_confidence_records:
            key = f"{record.industry}|{record.recommendation}|{record.score}|{record.pain_point[:80]}"

            if key in seen:
                continue

            seen.add(key)

            lines.append(
                "- "
                f"{record.industry} | "
                f"{record.recommendation} | "
                f"score={record.score} | "
                f"{record.pain_point[:120]}"
            )

            if len(lines) >= 10:
                break

        return "\n".join(lines) or "- No unique high-confidence records yet."

    def _recommended_actions(self, summary: MemoryTrendSummary) -> str:
        if summary.total_records == 0:
            return "- Run research jobs to create Hermes memory records."

        if not summary.high_confidence_themes:
            return "- Collect more evidence before moving opportunities toward validation."

        return "\n".join(
            [
                "- Review high-confidence opportunity themes.",
                "- Prioritize themes with repeated records across industries or sources.",
                "- Validate strongest themes with additional non-Reddit sources.",
                "- Do not move to MVP planning until strategic validation and evidence are reviewed.",
            ]
        )

    def _normalize_path(self, path: str) -> str:
        try:
            return self.path_normalizer.normalize(path)
        except PathNormalizerError:
            return "[blocked unsafe path]"

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
