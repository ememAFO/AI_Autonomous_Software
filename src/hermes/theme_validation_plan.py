from dataclasses import dataclass
from pathlib import Path

from src.hermes.theme_validation_readiness import ThemeValidationReadiness
from src.utils.path_normalizer import PathNormalizerError, ProjectPathNormalizer


class ThemeValidationPlanError(Exception):
    pass


@dataclass(frozen=True)
class ThemeValidationPlan:
    theme: str
    readiness: str
    readiness_score: float
    output_path: str
    validation_goal: str
    target_users: list[str]
    hypotheses: list[str]
    validation_methods: list[str]
    success_criteria: list[str]
    failure_criteria: list[str]
    evidence_to_collect: list[str]
    risks_to_check: list[str]
    recommended_next_action: str


class ThemeValidationPlanGenerator:
    """
    Generates a lightweight market validation plan for validation-ready themes.

    Purpose:
    - prevent jumping from trend detection directly to MVP building
    - define what evidence must be collected before build approval
    - preserve a human-reviewable validation artifact

    This generator does NOT approve building.
    It only creates a validation plan.
    """

    DEFAULT_OUTPUT_DIR = Path("reports/intelligence/validation_plans")

    def __init__(self, output_dir: str | Path = DEFAULT_OUTPUT_DIR):
        self.output_dir = self._validate_output_dir(Path(output_dir))
        self.path_normalizer = ProjectPathNormalizer()
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def generate(
        self,
        readiness: ThemeValidationReadiness,
    ) -> ThemeValidationPlan:
        if readiness.readiness != "VALIDATION_READY":
            raise ThemeValidationPlanError(
                "Validation plan can only be generated for VALIDATION_READY themes"
            )

        plan = self._build_plan(readiness)
        output_path = self._safe_plan_path(readiness.theme)
        output_path.write_text(self._format_plan(plan), encoding="utf-8")

        return ThemeValidationPlan(
            theme=plan.theme,
            readiness=plan.readiness,
            readiness_score=plan.readiness_score,
            output_path=self.path_normalizer.normalize(str(output_path)),
            validation_goal=plan.validation_goal,
            target_users=plan.target_users,
            hypotheses=plan.hypotheses,
            validation_methods=plan.validation_methods,
            success_criteria=plan.success_criteria,
            failure_criteria=plan.failure_criteria,
            evidence_to_collect=plan.evidence_to_collect,
            risks_to_check=plan.risks_to_check,
            recommended_next_action=plan.recommended_next_action,
        )

    def _build_plan(
        self,
        readiness: ThemeValidationReadiness,
    ) -> ThemeValidationPlan:
        theme = readiness.theme

        if theme == "lead + follow up":
            return ThemeValidationPlan(
                theme=theme,
                readiness=readiness.readiness,
                readiness_score=readiness.readiness_score,
                output_path="",
                validation_goal=(
                    "Validate whether small sales/service teams have a recurring, "
                    "paid problem around slow manual lead follow-up."
                ),
                target_users=[
                    "Small service business owners",
                    "Solo operators handling inbound enquiries",
                    "Sales teams using simple CRM workflows",
                    "Agencies or local businesses losing leads after quotes",
                ],
                hypotheses=[
                    "Users lose revenue because manual follow-up is slow or inconsistent.",
                    "Users already try to solve this with spreadsheets, reminders, CRM tasks, or manual messages.",
                    "Users would pay for a simple tool that automates follow-up without replacing their current CRM.",
                    "The pain is strongest when leads come from quotes, forms, calls, or missed demos.",
                ],
                validation_methods=[
                    "Run 5 to 10 customer discovery interviews.",
                    "Create a landing page describing the lead recovery assistant.",
                    "Test one clear offer with a waitlist or enquiry form.",
                    "Search additional core evidence from G2/Capterra/CRM reviews.",
                    "Compare against existing CRM automation and follow-up tools.",
                ],
                success_criteria=[
                    "At least 5 target users confirm the problem happens weekly.",
                    "At least 3 users describe revenue, time, or missed-sales impact.",
                    "At least 3 users already use a workaround.",
                    "At least 2 users agree to join a waitlist or review a prototype.",
                    "Competition review shows a narrow niche angle still exists.",
                ],
                failure_criteria=[
                    "Users describe the issue as minor annoyance only.",
                    "Users already solve it fully with existing tools.",
                    "No clear willingness-to-pay or urgency signal appears.",
                    "The problem depends heavily on complex CRM integrations too early.",
                    "The niche is too broad or too saturated for a small MVP.",
                ],
                evidence_to_collect=[
                    "Interview notes",
                    "Exact user quotes",
                    "Current workaround examples",
                    "Estimated time or revenue lost",
                    "Competitor pricing and feature comparison",
                    "Landing page visits and conversion rate",
                    "Waitlist or prototype interest",
                ],
                risks_to_check=[
                    "CRM integration complexity",
                    "SMS/email compliance requirements",
                    "Spam or consent risks",
                    "Data privacy and customer-contact handling",
                    "Overlapping features in existing CRM tools",
                    "Low willingness to pay from very small businesses",
                ],
                recommended_next_action=(
                    "Run lightweight validation before any MVP planning. "
                    "Do not build until interview and waitlist evidence is reviewed."
                ),
            )

        return ThemeValidationPlan(
            theme=theme,
            readiness=readiness.readiness,
            readiness_score=readiness.readiness_score,
            output_path="",
            validation_goal=f"Validate whether '{theme}' is a recurring paid problem.",
            target_users=[
                "Users affected by the repeated theme",
                "Small teams with workflow pain",
                "Operators currently using manual workarounds",
            ],
            hypotheses=[
                "The theme represents a recurring operational problem.",
                "Users experience measurable cost, time loss, or revenue impact.",
                "Users would consider paying for a focused solution.",
            ],
            validation_methods=[
                "Run customer discovery interviews.",
                "Collect additional core evidence.",
                "Create a landing page or waitlist.",
                "Compare with existing solutions.",
            ],
            success_criteria=[
                "Multiple target users confirm the problem.",
                "Users describe current workarounds.",
                "Users show willingness to try or pay for a solution.",
            ],
            failure_criteria=[
                "Problem is only a minor annoyance.",
                "Existing tools already solve the pain well.",
                "No clear willingness-to-pay signal appears.",
            ],
            evidence_to_collect=[
                "User quotes",
                "Workaround examples",
                "Willingness-to-pay signals",
                "Competitor evidence",
            ],
            risks_to_check=[
                "Market saturation",
                "Build complexity",
                "Compliance or security risk",
                "Weak commercial signal",
            ],
            recommended_next_action="Validate before any MVP planning.",
        )

    def _format_plan(self, plan: ThemeValidationPlan) -> str:
        return f"""# Theme Validation Plan: {plan.theme}

## Summary

- Theme: {plan.theme}
- Readiness: {plan.readiness}
- Readiness Score: {plan.readiness_score}

## Validation Goal

{plan.validation_goal}

## Target Users

{self._format_list(plan.target_users)}

## Hypotheses

{self._format_list(plan.hypotheses)}

## Validation Methods

{self._format_list(plan.validation_methods)}

## Success Criteria

{self._format_list(plan.success_criteria)}

## Failure Criteria

{self._format_list(plan.failure_criteria)}

## Evidence To Collect

{self._format_list(plan.evidence_to_collect)}

## Risks To Check

{self._format_list(plan.risks_to_check)}

## Recommended Next Action

{plan.recommended_next_action}

## Governance Note

This validation plan does not approve MVP building. It only defines the evidence required before a human reviewer can consider moving the theme into build planning.
"""

    def _format_list(self, values: list[str]) -> str:
        if not values:
            return "- None recorded."

        return "\n".join(f"- {value}" for value in values)

    def _safe_plan_path(self, theme: str) -> Path:
        safe_theme = (
            theme.lower()
            .replace("+", "and")
            .replace("/", "-")
            .replace(" ", "_")
            .replace("__", "_")
        )

        report_path = (self.output_dir / f"{safe_theme}_validation_plan.md").resolve()

        if not self._is_within(report_path, self.output_dir):
            raise ThemeValidationPlanError("Unsafe validation plan path detected")

        return report_path

    def _validate_output_dir(self, output_dir: Path) -> Path:
        resolved = output_dir.resolve()
        project_root = Path.cwd().resolve()
        allowed_root = (project_root / "reports" / "intelligence").resolve()

        if not self._is_within(resolved, allowed_root):
            raise ThemeValidationPlanError(
                "Validation plans must stay inside reports/intelligence"
            )

        return resolved

    @staticmethod
    def _is_within(path: Path, root: Path) -> bool:
        try:
            path.relative_to(root)
            return True
        except ValueError:
            return False
