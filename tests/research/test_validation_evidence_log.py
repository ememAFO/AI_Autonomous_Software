import json
from pathlib import Path

import pytest

from src.hermes.validation_evidence_log import (
    ValidationEvidenceLog,
    ValidationEvidenceLogError,
)


PLAN_PATH = (
    "reports/intelligence/validation_plans/"
    "lead_and_follow_up_validation_plan.md"
)


def clean_path(path: str) -> None:
    file_path = Path(path)
    if file_path.exists():
        file_path.unlink()


def test_validation_evidence_log_adds_source_classified_entry():
    path = "reports/intelligence/test_validation_evidence_log.json"
    clean_path(path)
    log = ValidationEvidenceLog(log_path=path)

    entry = log.add_entry(
        theme="lead + follow up",
        validation_plan_path=PLAN_PATH,
        evidence_type="customer_interview",
        evidence_summary=(
            "A service business owner loses leads when follow-up is delayed."
        ),
        source_reference="interview_001",
        signal_strength="strong",
        supports_validation=True,
        source_trust=ValidationEvidenceLog.HUMAN_ATTESTED_FIRST_PARTY,
        notes="Anonymised first-party summary.",
    )

    assert entry.theme == "lead + follow up"
    assert entry.evidence_type == "customer_interview"
    assert entry.source_trust == "human_attested_first_party"
    assert entry.signal_strength == "strong"
    assert entry.supports_validation is True


def test_validation_evidence_log_requires_source_trust_for_new_entry():
    path = "reports/intelligence/test_validation_evidence_source_required.json"
    clean_path(path)
    log = ValidationEvidenceLog(log_path=path)

    with pytest.raises(ValidationEvidenceLogError, match="source_trust"):
        log.add_entry(
            theme="lead + follow up",
            validation_plan_path=PLAN_PATH,
            evidence_type="customer_interview",
            evidence_summary="A direct finding.",
            source_reference="interview_001",
            signal_strength="strong",
            supports_validation=True,
        )


def test_validation_evidence_log_loads_missing_source_trust_as_legacy_history():
    path = Path(
        "reports/intelligence/test_validation_evidence_legacy_history.json"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "evidence": [
                    {
                        "theme": "lead + follow up",
                        "validation_plan_path": PLAN_PATH,
                        "evidence_type": "customer_interview",
                        "evidence_summary": "Historical entry.",
                        "source_reference": "historical_001",
                        "signal_strength": "medium",
                        "supports_validation": True,
                        "timestamp": "2026-06-08T00:00:00+00:00",
                        "notes": "",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    entries = ValidationEvidenceLog(log_path=path).list_entries()

    assert entries[0].source_trust == "legacy_unverified"


def test_validation_evidence_log_blocks_public_dataset_as_customer_interview():
    path = (
        "reports/intelligence/"
        "test_validation_evidence_invalid_public_dataset_type.json"
    )
    clean_path(path)
    log = ValidationEvidenceLog(log_path=path)

    with pytest.raises(
        ValidationEvidenceLogError,
        match="public_dataset evidence",
    ):
        log.add_entry(
            theme="lead + follow up",
            validation_plan_path=PLAN_PATH,
            evidence_type="customer_interview",
            evidence_summary="A public review was positive.",
            source_reference="g2_review_001",
            signal_strength="medium",
            supports_validation=True,
            source_trust=ValidationEvidenceLog.PUBLIC_DATASET,
        )


def test_validation_evidence_log_blocks_new_legacy_unverified_entry():
    path = (
        "reports/intelligence/"
        "test_validation_evidence_new_legacy_unverified.json"
    )
    clean_path(path)
    log = ValidationEvidenceLog(log_path=path)

    with pytest.raises(
        ValidationEvidenceLogError,
        match="legacy_unverified",
    ):
        log.add_entry(
            theme="lead + follow up",
            validation_plan_path=PLAN_PATH,
            evidence_type="manual_research",
            evidence_summary="A historical review.",
            source_reference="old_review_001",
            signal_strength="weak",
            supports_validation=True,
            source_trust=ValidationEvidenceLog.LEGACY_UNVERIFIED,
        )


def test_validation_evidence_log_blocks_invalid_evidence_type():
    path = (
        "reports/intelligence/"
        "test_validation_evidence_invalid_type.json"
    )
    clean_path(path)
    log = ValidationEvidenceLog(log_path=path)

    with pytest.raises(ValidationEvidenceLogError):
        log.add_entry(
            theme="lead + follow up",
            validation_plan_path=PLAN_PATH,
            evidence_type="random_type",
            evidence_summary="Some evidence.",
            source_reference="source_001",
            signal_strength="strong",
            supports_validation=True,
            source_trust=ValidationEvidenceLog.HUMAN_ATTESTED_FIRST_PARTY,
        )


def test_validation_evidence_log_blocks_invalid_signal_strength():
    path = (
        "reports/intelligence/"
        "test_validation_evidence_invalid_signal.json"
    )
    clean_path(path)
    log = ValidationEvidenceLog(log_path=path)

    with pytest.raises(ValidationEvidenceLogError):
        log.add_entry(
            theme="lead + follow up",
            validation_plan_path=PLAN_PATH,
            evidence_type="customer_interview",
            evidence_summary="Some evidence.",
            source_reference="source_001",
            signal_strength="very strong",
            supports_validation=True,
            source_trust=ValidationEvidenceLog.HUMAN_ATTESTED_FIRST_PARTY,
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
    path = Path(
        "reports/intelligence/test_invalid_validation_evidence_log.json"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{not valid json", encoding="utf-8")

    log = ValidationEvidenceLog(log_path=path)

    with pytest.raises(ValidationEvidenceLogError):
        log.list_entries()
