from pathlib import Path

import pytest

from src.hermes.validation_competitor_evidence import (
    CompetitorEvidenceInput,
    ValidationCompetitorEvidenceError,
    ValidationCompetitorEvidenceLogger,
)
from src.hermes.validation_evidence_log import ValidationEvidenceLog


def clean_path(path: str) -> None:
    file_path = Path(path)

    if file_path.exists():
        file_path.unlink()


def make_log(
    path: str = "reports/intelligence/test_validation_competitor_evidence_log.json",
) -> ValidationEvidenceLog:
    clean_path(path)
    return ValidationEvidenceLog(log_path=path)


def make_evidence(**overrides) -> CompetitorEvidenceInput:
    data = {
        "theme": "lead + follow up",
        "validation_plan_path": (
            "reports/intelligence/validation_plans/"
            "lead_and_follow_up_validation_plan.md"
        ),
        "competitor_name": "Example CRM",
        "finding_summary": (
            "Existing CRM has follow-up reminders, but setup appears too complex "
            "for small service businesses."
        ),
        "source_reference": "https://example.com/crm/pricing",
        "signal_strength": "medium",
        "supports_validation": True,
        "notes": "Pricing and setup may create a niche gap.",
    }

    data.update(overrides)
    return CompetitorEvidenceInput(**data)


def test_validation_competitor_evidence_logger_logs_supporting_finding():
    log = make_log()
    logger = ValidationCompetitorEvidenceLogger(log)

    entry = logger.log_competitor_evidence(make_evidence())

    assert entry.theme == "lead + follow up"
    assert entry.evidence_type == "competitor_check"
    assert entry.signal_strength == "medium"
    assert entry.supports_validation is True
    assert "Competitor: Example CRM" in entry.evidence_summary
    assert "Secondary competitor-check evidence" in entry.notes


def test_validation_competitor_evidence_logger_logs_negative_finding():
    log = make_log(
        "reports/intelligence/test_validation_competitor_evidence_negative.json"
    )
    logger = ValidationCompetitorEvidenceLogger(log)

    entry = logger.log_competitor_evidence(
        make_evidence(
            finding_summary=(
                "Competitor already solves lead follow-up cheaply and simply."
            ),
            signal_strength="negative",
            supports_validation=False,
        )
    )

    assert entry.supports_validation is False
    assert entry.signal_strength == "negative"


def test_validation_competitor_evidence_logger_rejects_empty_competitor_name():
    log = make_log(
        "reports/intelligence/test_validation_competitor_evidence_empty_name.json"
    )
    logger = ValidationCompetitorEvidenceLogger(log)

    with pytest.raises(ValidationCompetitorEvidenceError):
        logger.log_competitor_evidence(make_evidence(competitor_name=""))


def test_validation_competitor_evidence_logger_rejects_empty_finding_summary():
    log = make_log(
        "reports/intelligence/test_validation_competitor_evidence_empty_finding.json"
    )
    logger = ValidationCompetitorEvidenceLogger(log)

    with pytest.raises(ValidationCompetitorEvidenceError):
        logger.log_competitor_evidence(make_evidence(finding_summary=""))


def test_validation_competitor_evidence_logger_rejects_invalid_signal_strength():
    log = make_log(
        "reports/intelligence/test_validation_competitor_evidence_invalid_signal.json"
    )
    logger = ValidationCompetitorEvidenceLogger(log)

    with pytest.raises(ValidationCompetitorEvidenceError):
        logger.log_competitor_evidence(
            make_evidence(signal_strength="very strong")
        )
