import pytest

from src.hermes.theme_validation_plan import (
    ThemeValidationPlanError,
    ThemeValidationPlanGenerator,
)
from src.hermes.theme_validation_readiness import ThemeValidationReadiness


def make_readiness(
    *,
    theme: str = "lead + follow up",
    readiness: str = "VALIDATION_READY",
) -> ThemeValidationReadiness:
    return ThemeValidationReadiness(
        theme=theme,
        readiness=readiness,
        readiness_score=67.61,
        reason="Theme has repeated evidence.",
        recommended_next_action="Create a lightweight validation plan before any MVP build.",
        risk_flags=[],
    )


def test_theme_validation_plan_generator_creates_plan_for_validation_ready_theme():
    generator = ThemeValidationPlanGenerator(
        output_dir="reports/intelligence/test_validation_plans"
    )

    plan = generator.generate(make_readiness())

    assert plan.theme == "lead + follow up"
    assert plan.readiness == "VALIDATION_READY"
    assert "lead" in plan.validation_goal.lower()
    assert plan.target_users
    assert plan.hypotheses
    assert plan.success_criteria
    assert plan.failure_criteria
    assert plan.output_path.endswith("lead_and_follow_up_validation_plan.md")


def test_theme_validation_plan_generator_writes_markdown_report():
    generator = ThemeValidationPlanGenerator(
        output_dir="reports/intelligence/test_validation_plans"
    )

    plan = generator.generate(make_readiness())

    from pathlib import Path

    content = Path(plan.output_path).read_text(encoding="utf-8")

    assert "# Theme Validation Plan: lead + follow up" in content
    assert "Validation Goal" in content
    assert "Success Criteria" in content
    assert "Governance Note" in content
    assert "does not approve MVP building" in content


def test_theme_validation_plan_generator_blocks_non_ready_theme():
    generator = ThemeValidationPlanGenerator(
        output_dir="reports/intelligence/test_validation_plans"
    )

    with pytest.raises(ThemeValidationPlanError):
        generator.generate(make_readiness(readiness="WATCH"))


def test_theme_validation_plan_generator_blocks_unsafe_output_dir():
    with pytest.raises(ThemeValidationPlanError):
        ThemeValidationPlanGenerator(output_dir="../../unsafe")

def test_theme_validation_plan_generator_blocks_sibling_prefix_output_dir():
    with pytest.raises(ThemeValidationPlanError):
        ThemeValidationPlanGenerator(
            output_dir="reports/intelligence_backup/test_validation_plans"
        )
