from dataclasses import dataclass
from pathlib import Path


class ValidationCompetitorCheckError(Exception):
    pass


@dataclass(frozen=True)
class CompetitorCheck:
    theme: str
    target_user: str
    competitor_categories: list[str]
    competitor_questions: list[str]
    comparison_criteria: list[str]
    risk_questions: list[str]
    evidence_logging_guidance: list[str]
    recommended_next_action: str
    warning: str


class ValidationCompetitorCheckGenerator:
    """
    Generates a structured competitor-check template for agent-assisted validation.

    Purpose:
    - collect secondary validation evidence
    - compare existing alternatives
    - identify saturation, complexity, and differentiation risks
    - avoid treating competitor research as direct customer proof

    This does not approve human review or build planning.
    """

    def generate(
        self,
        *,
        theme: str,
        target_user: str = "small service business owner",
    ) -> CompetitorCheck:
        if not theme.strip():
            raise ValidationCompetitorCheckError("Theme is required")

        if not target_user.strip():
            raise ValidationCompetitorCheckError("Target user is required")

        if theme.strip().lower() == "lead + follow up":
            return CompetitorCheck(
                theme=theme.strip(),
                target_user=target_user.strip(),
                competitor_categories=[
                    "CRM tools with follow-up reminders",
                    "Email automation tools",
                    "SMS/WhatsApp follow-up tools",
                    "Calendar/task reminder tools",
                    "Lead capture and booking tools",
                    "No-code automation tools such as Zapier-style workflows",
                ],
                competitor_questions=[
                    "Which tools already help this user follow up with leads?",
                    "Do those tools solve the problem fully or only partially?",
                    "Are users complaining about setup complexity, cost, integrations, or reliability?",
                    "Are small service businesses the main target, or are the tools built for larger sales teams?",
                    "Is follow-up automation a core feature or a buried feature?",
                    "Do competitors support the channels users actually use, such as WhatsApp, SMS, email, phone reminders, or CRM tasks?",
                ],
                comparison_criteria=[
                    "Target customer fit",
                    "Ease of setup",
                    "Pricing fit for small businesses",
                    "Supported communication channels",
                    "CRM/integration requirements",
                    "Reminder and automation flexibility",
                    "Evidence of customer complaints",
                    "Differentiation opportunity",
                ],
                risk_questions=[
                    "Is the market already saturated with simple follow-up tools?",
                    "Would this require too many integrations too early?",
                    "Would spam, consent, or privacy concerns limit the product?",
                    "Is the pain already solved well enough by existing CRMs?",
                    "Is the user segment too unwilling to pay?",
                    "Would the product become a generic CRM instead of a focused tool?",
                ],
                evidence_logging_guidance=[
                    "Log competitor findings as competitor_check evidence, not customer proof.",
                    "Record whether the finding supports or weakens the theme.",
                    "Use strong signal only when competitors clearly leave a gap for the target user.",
                    "Use negative signal if competitors already solve the pain cheaply and simply.",
                    "Capture source references such as product pages, review summaries, or pricing pages.",
                    "Do not move to human review based only on competitor research.",
                ],
                recommended_next_action=(
                    "Use this check to find market gaps and risks, then combine it with "
                    "real customer interviews before running the ValidationGate again."
                ),
                warning=(
                    "Competitor research is secondary evidence. It can show market structure "
                    "and gaps, but it cannot prove willingness to pay."
                ),
            )

        return CompetitorCheck(
            theme=theme.strip(),
            target_user=target_user.strip(),
            competitor_categories=[
                "Direct competitors",
                "Indirect alternatives",
                "Manual workarounds",
                "No-code or automation-based substitutes",
            ],
            competitor_questions=[
                "Which tools already solve this problem?",
                "Who are those tools built for?",
                "What complaints appear repeatedly in public reviews?",
                "What parts of the problem remain unsolved?",
                "Is there a clear niche that existing tools ignore?",
            ],
            comparison_criteria=[
                "Target customer fit",
                "Pricing",
                "Ease of use",
                "Feature coverage",
                "Setup complexity",
                "Customer complaints",
                "Differentiation opportunity",
            ],
            risk_questions=[
                "Is the market saturated?",
                "Is the problem already solved well enough?",
                "Would the build be too complex?",
                "Is willingness to pay unclear?",
            ],
            evidence_logging_guidance=[
                "Log findings as competitor_check evidence.",
                "Separate support signals from counter-evidence.",
                "Do not treat competitor research as direct customer validation.",
            ],
            recommended_next_action=(
                "Collect competitor evidence, then combine it with customer evidence."
            ),
            warning=(
                "This is secondary evidence only. It does not approve human review or build planning."
            ),
        )

    def format_markdown(self, check: CompetitorCheck) -> str:
        return f"""# Validation Competitor Check: {check.theme}

## Target User

{check.target_user}

## Warning

{check.warning}

## Competitor Categories To Review

{self._format_list(check.competitor_categories)}

## Competitor Research Questions

{self._format_list(check.competitor_questions)}

## Comparison Criteria

{self._format_list(check.comparison_criteria)}

## Risk / Counter-Evidence Questions

{self._format_list(check.risk_questions)}

## Evidence Logging Guidance

{self._format_list(check.evidence_logging_guidance)}

## Recommended Next Action

{check.recommended_next_action}

## Governance Note

This competitor check does not approve human review or build planning. It only helps collect secondary validation evidence that can later be logged and assessed by the ValidationGate.
"""

    def write_markdown(
        self,
        *,
        theme: str,
        target_user: str,
        output_path: str | Path,
    ) -> Path:
        path = Path(output_path)
        self._validate_output_path(path)
        path.parent.mkdir(parents=True, exist_ok=True)

        check = self.generate(theme=theme, target_user=target_user)
        path.write_text(self.format_markdown(check), encoding="utf-8")

        return path

    def _format_list(self, values: list[str]) -> str:
        if not values:
            return "- None."

        return "\n".join(f"- {value}" for value in values)

    def _validate_output_path(self, output_path: Path) -> None:
        resolved = output_path.resolve()
        project_root = Path.cwd().resolve()
        allowed_root = (project_root / "reports" / "intelligence").resolve()

        if not str(resolved).startswith(str(allowed_root)):
            raise ValidationCompetitorCheckError(
                "Validation competitor check must be written inside reports/intelligence"
            )

        if resolved.suffix != ".md":
            raise ValidationCompetitorCheckError(
                "Validation competitor check must be a Markdown file"
            )
