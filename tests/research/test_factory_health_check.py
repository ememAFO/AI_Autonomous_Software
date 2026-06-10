from pathlib import Path

from src.hermes.factory_health_check import FactoryHealthChecker
from src.hermes.theme_state_registry import ThemeStateRegistry
from src.hermes.theme_validation_plan import ThemeValidationPlan
from src.hermes.theme_validation_plan_registry import ThemeValidationPlanRegistry
from src.hermes.validation_evidence_log import ValidationEvidenceLog


def clean_path(path: str) -> None:
    file_path = Path(path)

    if file_path.exists():
        file_path.unlink()


def make_state_registry(
    path: str = "reports/intelligence/test_factory_health_state_registry.json",
) -> ThemeStateRegistry:
    clean_path(path)
    return ThemeStateRegistry(registry_path=path)


def make_plan_registry(
    path: str = "reports/intelligence/test_factory_health_plan_registry.json",
) -> ThemeValidationPlanRegistry:
    clean_path(path)
    return ThemeValidationPlanRegistry(registry_path=path)


def make_evidence_log(
    path: str = "reports/intelligence/test_factory_health_evidence_log.json",
) -> ValidationEvidenceLog:
    clean_path(path)
    return ValidationEvidenceLog(log_path=path)


def make_plan(output_path: str) -> ThemeValidationPlan:
    return ThemeValidationPlan(
        theme="lead + follow up",
        readiness="VALIDATION_READY",
        readiness_score=68.27,
        output_path=output_path,
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


def register_theme(registry: ThemeStateRegistry) -> None:
    registry.register_theme(
        theme_id="lead_follow_up_001",
        theme_name="lead + follow up",
        trigger="trend_detected",
        reason="Repeated lead follow-up pain found.",
        changed_by="HermesMemoryTrendDetector",
        related_artifact_id="trend_report_001",
        policy_version="2026-06-08.v1",
        run_id="factory_health_test_001",
    )


def test_factory_health_check_passes_for_valid_registries():
    plan_path = Path(
        "reports/intelligence/test_validation_plans/"
        "lead_and_follow_up_validation_plan.md"
    )
    plan_path.parent.mkdir(parents=True, exist_ok=True)
    plan_path.write_text("# Test validation plan", encoding="utf-8")

    state_registry = make_state_registry()
    plan_registry = make_plan_registry()
    evidence_log = make_evidence_log()

    register_theme(state_registry)
    plan_registry.add_plan(make_plan(str(plan_path)))

    evidence_log.add_entry(
        theme="lead + follow up",
        validation_plan_path=str(plan_path),
        evidence_type="customer_interview",
        evidence_summary="User confirmed delayed follow-up creates lost sales.",
        source_reference="Interview 1",
        signal_strength="strong",
        supports_validation=True,
    )

    report = FactoryHealthChecker(
        state_registry=state_registry,
        validation_plan_registry=plan_registry,
        validation_evidence_log=evidence_log,
    ).run()

    assert report.status == "PASS"
    assert report.passed is True
    assert all(result.status == "PASS" for result in report.results)


def test_factory_health_check_fails_when_state_registry_integrity_is_broken():
    state_registry_path = (
        "reports/intelligence/test_factory_health_broken_state_registry.json"
    )

    state_registry = make_state_registry(state_registry_path)
    plan_registry = make_plan_registry(
        "reports/intelligence/test_factory_health_broken_plan_registry.json"
    )
    evidence_log = make_evidence_log(
        "reports/intelligence/test_factory_health_broken_evidence_log.json"
    )

    register_theme(state_registry)

    path = Path(state_registry_path)
    tampered = path.read_text(encoding="utf-8").replace(
        "lead + follow up",
        "tampered theme",
    )
    path.write_text(tampered, encoding="utf-8")

    report = FactoryHealthChecker(
        state_registry=state_registry,
        validation_plan_registry=plan_registry,
        validation_evidence_log=evidence_log,
    ).run()

    assert report.status == "FAIL"
    assert any(
        result.check_name == "theme_state_registry_integrity"
        and result.status == "FAIL"
        for result in report.results
    )


def test_factory_health_check_fails_when_evidence_references_missing_plan():
    state_registry = make_state_registry(
        "reports/intelligence/test_factory_health_missing_plan_state_registry.json"
    )
    plan_registry = make_plan_registry(
        "reports/intelligence/test_factory_health_missing_plan_plan_registry.json"
    )
    evidence_log = make_evidence_log(
        "reports/intelligence/test_factory_health_missing_plan_evidence_log.json"
    )

    register_theme(state_registry)

    evidence_log.add_entry(
        theme="lead + follow up",
        validation_plan_path=(
            "reports/intelligence/test_validation_plans/missing_plan.md"
        ),
        evidence_type="customer_interview",
        evidence_summary="User confirmed delayed follow-up creates lost sales.",
        source_reference="Interview 1",
        signal_strength="strong",
        supports_validation=True,
    )

    report = FactoryHealthChecker(
        state_registry=state_registry,
        validation_plan_registry=plan_registry,
        validation_evidence_log=evidence_log,
    ).run()

    assert report.status == "FAIL"
    assert any(
        result.check_name == "validation_evidence_plan_links"
        and result.status == "FAIL"
        for result in report.results
    )
