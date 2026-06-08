from pathlib import Path

import pytest

from src.hermes.validation_evidence_log import (
    ValidationEvidenceLog,
    ValidationEvidenceLogError,
)


def test_validation_evidence_log_adds_entry():
    log = ValidationEvidenceLog(
        log_path="reports/intelligence/test_validation_evidence_log.json"
    )

    entry = log.add_entry(
        theme="lead + follow up",
        validation_plan_path=(
            "reports/intelligence/validation_plans/"
            "lead_and_follow_up_validation_plan.md"
        ),
        evidence_type="customer_interview",
        evidence_summary="A service business owner loses leads when follow-up is delayed.",
        source_reference="Interview 001",
        signal_strength="strong",
        supports_validation=True,
        notes="User currently follows up manually with WhatsApp.",
    )

    assert entry.theme == "lead + follow up"
    assert entry.evidence_type == "customer_interview"
    assert entry.signal_strength == "strong"
    assert entry.supports_validation is True


def test_validation_evidence_log_lists_entries_for_theme():
    log = ValidationEvidenceLog(
        log_path="reports/intelligence/test_validation_evidence_log_theme.json"
    )

    log.add_entry(
        theme="lead + follow up",
        validation_plan_path=(
            "reports/intelligence/validation_plans/"
            "lead_and_follow_up_validation_plan.md"
        ),
        evidence_type="willingness_to_pay",
        evidence_summary="User said they would pay for automated quote follow-up.",
        source_reference="Interview 002",
        signal_strength="medium",
        supports_validation=True,
    )

    entries = log.list_entries_for_theme("lead + follow up")

    assert entries
    assert entries[-1].theme == "lead + follow up"


def test_validation_evidence_log_blocks_invalid_evidence_type():
    log = ValidationEvidenceLog(
        log_path="reports/intelligence/test_validation_evidence_invalid_type.json"
    )

    with pytest.raises(ValidationEvidenceLogError):
        log.add_entry(
            theme="lead + follow up",
            validation_plan_path=(
                "reports/intelligence/validation_plans/"
                "lead_and_follow_up_validation_plan.md"
            ),
            evidence_type="random_type",
            evidence_summary="Some evidence.",
            source_reference="Source",
            signal_strength="strong",
            supports_validation=True,
        )


def test_validation_evidence_log_blocks_invalid_signal_strength():
    log = ValidationEvidenceLog(
        log_path="reports/intelligence/test_validation_evidence_invalid_signal.json"
    )

    with pytest.raises(ValidationEvidenceLogError):
        log.add_entry(
            theme="lead + follow up",
            validation_plan_path=(
                "reports/intelligence/validation_plans/"
                "lead_and_follow_up_validation_plan.md"
            ),
            evidence_type="customer_interview",
            evidence_summary="Some evidence.",
            source_reference="Source",
            signal_strength="very strong",
            supports_validation=True,
        )


def test_validation_evidence_log_blocks_unsafe_log_path():
    with pytest.raises(ValidationEvidenceLogError):
        ValidationEvidenceLog(log_path="../../unsafe.json")


def test_validation_evidence_log_blocks_non_json_log_path():
    with pytest.raises(ValidationEvidenceLogError):
        ValidationEvidenceLog(
            log_path="reports/intelligence/test_validation_evidence_log.txt"
        )


def test_validation_evidence_log_blocks_invalid_json():
    path = Path("reports/intelligence/test_invalid_validation_evidence_log.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{not valid json", encoding="utf-8")

    log = ValidationEvidenceLog(log_path=path)

    with pytest.raises(ValidationEvidenceLogError):
        log.list_entries()
