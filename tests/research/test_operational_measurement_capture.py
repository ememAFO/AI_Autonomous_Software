from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.research.operational_measurement_capture import (
    OperationalMeasurementCaptureError,
    OperationalMeasurementCaptureService,
)

PROGRAM = "EOP-0001-QUOTE-OUTCOME-MEASUREMENT-0-1"
CAMPAIGN = "EOP-0001-FPV-20260805"


def policy_payload() -> dict:
    return {
        "policy_id": "POLICY-OM-1",
        "campaign_id": CAMPAIGN,
        "measurement_program_id": PROGRAM,
        "theme": "lead + follow up",
        "minimum_baseline_days": 14,
        "minimum_observation_days": 14,
        "minimum_sample_size": 5,
        "allowed_comparison_methods": [
            "descriptive_before_after",
            "matched_period",
        ],
        "allowed_decisions": [
            "continue",
            "adapt",
            "pause",
            "stop",
            "insufficient_evidence",
        ],
        "metrics": {
            "unclassified_rate_percent": {
                "unit": "percent",
                "improvement_direction": "decrease_is_better",
                "materiality_threshold": 2.0,
            },
            "accepted_rate_percent": {
                "unit": "percent",
                "improvement_direction": "increase_is_better",
                "materiality_threshold": 2.0,
            },
        },
        "allowed_operational_context_codes": [
            "mixed_quote_portfolio",
            "domestic",
        ],
        "allowed_confounder_codes": [
            "none_known",
            "lead_mix_change",
            "other_documented",
        ],
        "allowed_feedback_reason_codes": [
            "useful_recommendation",
            "wrong_classification",
            "no_feedback_recorded",
        ],
        "allowed_unintended_effect_codes": [
            "none_observed",
            "alert_fatigue",
        ],
    }


def measurement(**overrides) -> dict:
    payload = {
        "campaign_id": CAMPAIGN,
        "measurement_program_id": PROGRAM,
        "measurement_id": "MEASURE-001",
        "pilot_id": "PILOT-001",
        "metric_name": "unclassified_rate_percent",
        "comparison_method": "descriptive_before_after",
        "baseline_start": "2026-07-01",
        "baseline_end": "2026-07-14",
        "intervention_start": "2026-07-15",
        "observation_end": "2026-07-28",
        "baseline_sample_size": 10,
        "observation_sample_size": 12,
        "operational_context_codes": [
            "mixed_quote_portfolio"
        ],
        "operational_context_summary": (
            "The pilot covered a mixed portfolio of domestic quotation "
            "work with the same staff process during both periods."
        ),
        "known_confounders": ["none_known"],
        "outcome_before": 42.0,
        "outcome_after": 30.0,
        "persistence_period_days": 14,
        "estimated_financial_effect_gbp": 250.0,
        "manual_time_before_minutes": 12.0,
        "manual_time_after_minutes": 8.0,
        "feedback_reason_codes": ["useful_recommendation"],
        "unintended_effect_codes": ["none_observed"],
        "expert_interpretation": (
            "The observed reduction is promising but remains an "
            "uncontrolled association rather than a causal result."
        ),
        "decision_taken": "continue",
        "source_reference": "WORKBOOK-001",
        "captured_at": "2026-07-28T17:00:00+01:00",
        "provenance_attested": True,
        "attestor_reference": "EMEM-REVIEW-001",
        "synthetic_measurement": False,
    }
    payload.update(overrides)
    return payload


def setup_project(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> Path:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "config").mkdir()
    policy = tmp_path / "config/policy.json"
    policy.write_text(
        json.dumps(policy_payload()),
        encoding="utf-8",
    )
    (tmp_path / "data/manual").mkdir(parents=True)
    return policy


def write_input(tmp_path: Path, payload: object) -> Path:
    path = tmp_path / "data/manual/measurements.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def capture_one(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    record: dict | None = None,
):
    policy = setup_project(tmp_path, monkeypatch)
    input_path = write_input(
        tmp_path,
        {"measurements": [record or measurement()]},
    )
    report = OperationalMeasurementCaptureService().capture(
        input_file=input_path,
        policy_file=policy,
        output_file=Path(
            "reports/research/operational_measurement_capture/"
            "capture.json"
        ),
    )
    return policy, report


def test_capture_derives_effect_and_preserves_boundary(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, report = capture_one(tmp_path, monkeypatch)
    assert report["accepted"] == 1
    assert report["blocked"] == 0
    assert report["validation_log_import_allowed"] is False
    candidate_path = Path(report["candidate_path"])
    candidate = json.loads(
        candidate_path.read_text(encoding="utf-8").strip()
    )
    assert candidate["effect_direction"] == "improvement"
    assert candidate["effect_magnitude"] == 12.0
    assert candidate["absolute_change"] == -12.0
    assert candidate["persistence_period_days"] == 14
    assert candidate["validation_log_import_allowed"] is False


def test_capture_blocks_forbidden_identifier_field(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, report = capture_one(
        tmp_path,
        monkeypatch,
        measurement(customer_email="person@example.com"),
    )
    assert report["accepted"] == 0
    reasons = report["blocked_measurements"][0][
        "blocking_reasons"
    ]
    assert "forbidden_fields:customer_email" in reasons


def test_capture_blocks_contact_detail_in_narrative(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, report = capture_one(
        tmp_path,
        monkeypatch,
        measurement(
            expert_interpretation=(
                "The result was reviewed by person@example.com and "
                "appeared positive, but this text contains contact data."
            )
        ),
    )
    reasons = report["blocked_measurements"][0][
        "blocking_reasons"
    ]
    assert (
        "email_detected_in_expert_interpretation" in reasons
    )


def test_capture_blocks_invalid_period_order(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, report = capture_one(
        tmp_path,
        monkeypatch,
        measurement(intervention_start="2026-07-10"),
    )
    reasons = report["blocked_measurements"][0][
        "blocking_reasons"
    ]
    assert "measurement_period_order_invalid" in reasons


def test_capture_blocks_unsupported_feedback_code(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, report = capture_one(
        tmp_path,
        monkeypatch,
        measurement(feedback_reason_codes=["invented_reason"]),
    )
    reasons = report["blocked_measurements"][0][
        "blocking_reasons"
    ]
    assert any(
        reason.startswith("feedback_reason_codes_unsupported")
        for reason in reasons
    )


def test_capture_blocks_short_windows_and_small_samples(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, report = capture_one(
        tmp_path,
        monkeypatch,
        measurement(
            baseline_end="2026-07-05",
            intervention_start="2026-07-06",
            observation_end="2026-07-10",
            baseline_sample_size=2,
            observation_sample_size=3,
            persistence_period_days=5,
        ),
    )
    reasons = report["blocked_measurements"][0][
        "blocking_reasons"
    ]
    assert "baseline_period_too_short" in reasons
    assert "observation_period_too_short" in reasons
    assert "baseline_sample_size_too_small" in reasons
    assert "observation_sample_size_too_small" in reasons


def test_capture_blocks_synthetic_measurement(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, report = capture_one(
        tmp_path,
        monkeypatch,
        measurement(synthetic_measurement=True),
    )
    reasons = report["blocked_measurements"][0][
        "blocking_reasons"
    ]
    assert "synthetic_measurement_not_allowed" in reasons


def test_capture_rejects_duplicate_batch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    policy = setup_project(tmp_path, monkeypatch)
    input_path = write_input(
        tmp_path,
        {"measurements": [measurement()]},
    )
    service = OperationalMeasurementCaptureService()
    service.capture(
        input_file=input_path,
        policy_file=policy,
        output_file=Path(
            "reports/research/operational_measurement_capture/one.json"
        ),
    )
    with pytest.raises(
        OperationalMeasurementCaptureError,
        match="already been processed",
    ):
        service.capture(
            input_file=input_path,
            policy_file=policy,
            output_file=Path(
                "reports/research/operational_measurement_capture/"
                "two.json"
            ),
        )


def test_capture_blocks_none_known_mixed_with_confounder(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, report = capture_one(
        tmp_path,
        monkeypatch,
        measurement(
            known_confounders=[
                "none_known",
                "lead_mix_change",
            ]
        ),
    )
    reasons = report["blocked_measurements"][0][
        "blocking_reasons"
    ]
    assert "none_known_cannot_mix_with_confounders" in reasons
