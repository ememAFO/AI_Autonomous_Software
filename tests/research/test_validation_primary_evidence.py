from pathlib import Path

import pytest

from src.hermes.validation_evidence_log import ValidationEvidenceLog
from src.hermes.validation_primary_evidence import (
    PrimaryEvidenceInput,
    ValidationPrimaryEvidenceError,
    ValidationPrimaryEvidenceLogger,
)


def clean_path(path: str) -> None:
    file_path = Path(path)

    if file_path.exists():
        file_path.unlink()


def make_log(
    path: str = "reports/intelligence/test_validation_primary_evidence_log.json",
) -> ValidationEvidenceLog:
    clean_path(path)
    return ValidationEvidenceLog(log_path=path)


def make_evidence(**overrides) -> PrimaryEvidenceInput:
    data = {
        "theme": "lead + follow up",
        "validation_plan_path": (
            "reports/intelligence/validation_plans/"
            "lead_and_follow_up_validation_plan.md"
        ),
        "evidence_type": "customer_interview",
        "participant_reference": "small_business_owner_002",
        "finding_summary": (
            "Owner said delayed WhatsApp follow-ups cause missed bookings."
        ),
        "source_reference": "manual_interview_002",
        "signal_strength": "strong",
        "supports_validation": True,
        "notes": "Direct customer interview.",
    }

    data.update(overrides)
    return PrimaryEvidenceInput(**data)


def test_validation_primary_evidence_logger_logs_customer_interview():
    log = make_log()
    logger = ValidationPrimaryEvidenceLogger(log)

    entry = logger.log_primary_evidence(make_evidence())

    assert entry.theme == "lead + follow up"
    assert entry.evidence_type == "customer_interview"
    assert entry.signal_strength == "strong"
    assert entry.supports_validation is True
    assert "Participant/Signal: small_business_owner_002" in entry.evidence_summary
    assert "Primary validation evidence" in entry.notes


def test_validation_primary_evidence_logger_logs_willingness_to_pay():
    log = make_log(
        "reports/intelligence/test_validation_primary_evidence_wtp.json"
    )
    logger = ValidationPrimaryEvidenceLogger(log)

    entry = logger.log_primary_evidence(
        make_evidence(
            evidence_type="willingness_to_pay",
            finding_summary=(
                "Owner said they would pay £15/month if the tool recovered missed leads."
            ),
            source_reference="manual_wtp_interview_001",
            notes="Direct willingness-to-pay signal.",
        )
    )

    assert entry.evidence_type == "willingness_to_pay"
    assert entry.supports_validation is True
    assert "£15/month" in entry.evidence_summary


def test_validation_primary_evidence_logger_rejects_secondary_evidence_type():
    log = make_log(
        "reports/intelligence/test_validation_primary_evidence_secondary.json"
    )
    logger = ValidationPrimaryEvidenceLogger(log)

    with pytest.raises(ValidationPrimaryEvidenceError):
        logger.log_primary_evidence(
            make_evidence(evidence_type="competitor_check")
        )


def test_validation_primary_evidence_logger_rejects_risk_evidence_type():
    log = make_log(
        "reports/intelligence/test_validation_primary_evidence_risk.json"
    )
    logger = ValidationPrimaryEvidenceLogger(log)

    with pytest.raises(ValidationPrimaryEvidenceError):
        logger.log_primary_evidence(
            make_evidence(evidence_type="risk_finding")
        )


def test_validation_primary_evidence_logger_rejects_empty_participant_reference():
    log = make_log(
        "reports/intelligence/test_validation_primary_evidence_empty_participant.json"
    )
    logger = ValidationPrimaryEvidenceLogger(log)

    with pytest.raises(ValidationPrimaryEvidenceError):
        logger.log_primary_evidence(
            make_evidence(participant_reference="")
        )


def test_validation_primary_evidence_logger_rejects_invalid_signal_strength():
    log = make_log(
        "reports/intelligence/test_validation_primary_evidence_invalid_signal.json"
    )
    logger = ValidationPrimaryEvidenceLogger(log)

    with pytest.raises(ValidationPrimaryEvidenceError):
        logger.log_primary_evidence(
            make_evidence(signal_strength="very strong")
        )
