from pathlib import Path

from src.research.scoring import OpportunityScore


class OpportunityReportGenerator:
    """
    Generates Markdown reports for scored opportunities.

    Security rules:
    - Reports must stay inside the allowed reports directory.
    - Filenames are sanitized.
    - Path traversal is blocked.
    """

    DEFAULT_OUTPUT_DIR = Path("reports/opportunities")

    def __init__(self, output_dir: str | Path = DEFAULT_OUTPUT_DIR):
        self.output_dir = self._validate_output_dir(Path(output_dir))
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def generate(self, score: OpportunityScore) -> Path:
        opportunity = score.opportunity
        filename = self._safe_filename(opportunity.title)
        report_path = self._safe_report_path(filename)

        evidence = "\n".join(f"- {item}" for item in opportunity.evidence) or "- No evidence provided yet."
        reasons = "\n".join(f"- {reason}" for reason in score.reasons) or "- No scoring reasons provided."

        content = f"""# Opportunity Report: {opportunity.title}

## Recommendation

**{score.recommendation}**

## Total Score

**{score.total_score}/10**

## Industry

{opportunity.industry}

## Source

{opportunity.source.value}

## Pain Point

{opportunity.pain_point}

## Suggested MVP

{opportunity.suggested_mvp or "No MVP suggestion provided yet."}

## Evidence

{evidence}

## Scoring Breakdown

- Frequency: {opportunity.frequency}/10
- Urgency: {opportunity.urgency}/10
- Monetization: {opportunity.monetization}/10
- Retention Impact: {opportunity.retention_impact}/10
- Competition Gap: {opportunity.competition_gap}/10
- Automation Potential: {opportunity.automation_potential}/10
- Implementation Difficulty: {opportunity.implementation_difficulty}/10

## Scoring Reasons

{reasons}

## Next Action

{self._next_action(score.recommendation)}
"""

        report_path.write_text(content, encoding="utf-8")
        return report_path

    def _validate_output_dir(self, output_dir: Path) -> Path:
        resolved = output_dir.resolve()
        project_root = Path.cwd().resolve()
        reports_root = (project_root / "reports").resolve()

        if not str(resolved).startswith(str(reports_root)):
            raise ValueError("Report output directory must stay inside the reports folder")

        return resolved

    def _safe_report_path(self, filename: str) -> Path:
        report_path = (self.output_dir / f"{filename}.md").resolve()

        if not str(report_path).startswith(str(self.output_dir)):
            raise ValueError("Unsafe report path detected")

        return report_path

    def _safe_filename(self, title: str) -> str:
        safe = title.lower().strip()
        safe = safe.replace(" ", "_")
        safe = "".join(char for char in safe if char.isalnum() or char in {"_", "-"})
        return safe or "opportunity_report"

    def _next_action(self, recommendation: str) -> str:
        if recommendation == "BUILD_NOW":
            return "Move this opportunity into validation and MVP planning."
        if recommendation == "VALIDATE_FIRST":
            return "Collect more evidence before planning an MVP."
        if recommendation == "WATCH":
            return "Track this opportunity but do not build yet."
        return "Reject this opportunity for now."
