from pathlib import Path

import pytest

from src.hermes.theme_validation_plan import ThemeValidationPlan
from src.hermes.theme_validation_plan_registry import (
    ThemeValidationPlanRegistry,
    ThemeValidationPlanRegistryError,
)


def make_plan() -> ThemeValidationPlan:
    return ThemeValidationPlan(
        theme="lead + follow up",
        readiness="VALIDATION_READY",
        readiness_score=68.27,
        output_path="reports/intelligence/validation_plans/lead_and_follow_up_validation_plan.md",
        validation_goal="Validate lead follow-up pain.",
        target_users=["Small service business owners"],
        hypotheses=["Manual follow-up causes lost leads."],
        validation_methods=["Customer interviews"],
        success_criteria=["Users confirm weekly pain."],
        failure_criteria=["No willingness to pay."],
        evidence_to_collect=["Interview notes"],
        risks_to_check=["CRM integration complexity"],
        recommended_next_action="Validate before MVP planning.",
    )


def test_theme_validation_plan_registry_adds_plan_entry():
    registry = ThemeValidationPlanRegistry(
        registry_path="reports/intelligence/test_validation_plan_index.json"
    )

    entry = registry.add_plan(make_plan())

    assert entry.theme == "lead + follow up"
    assert entry.readiness == "VALIDATION_READY"
    assert entry.status == "planned"
    assert entry.output_path.endswith("lead_and_follow_up_validation_plan.md")


def test_theme_validation_plan_registry_lists_entries():
    registry_path = "reports/intelligence/test_validation_plan_index_list.json"
    registry = ThemeValidationPlanRegistry(registry_path=registry_path)

    registry.add_plan(make_plan())

    entries = registry.list_entries()

    assert len(entries) >= 1
    assert entries[-1].theme == "lead + follow up"


def test_theme_validation_plan_registry_blocks_unsafe_path():
    with pytest.raises(ThemeValidationPlanRegistryError):
        ThemeValidationPlanRegistry(registry_path="../../unsafe.json")


def test_theme_validation_plan_registry_blocks_non_json_file():
    with pytest.raises(ThemeValidationPlanRegistryError):
        ThemeValidationPlanRegistry(
            registry_path="reports/intelligence/test_validation_plan_index.txt"
        )


def test_theme_validation_plan_registry_blocks_invalid_json():
    path = Path("reports/intelligence/test_invalid_validation_plan_index.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{not valid json", encoding="utf-8")

    registry = ThemeValidationPlanRegistry(registry_path=path)

    with pytest.raises(ThemeValidationPlanRegistryError):
        registry.list_entries()
