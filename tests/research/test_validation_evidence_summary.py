from src.hermes.validation_evidence_log import ValidationEvidenceEntry
from src.hermes.validation_evidence_summary import ValidationEvidenceSummarizer


def make_entry(
    *,
    supports_validation: bool = True,
    signal_strength: str = "strong",
    evidence_type: str = "customer_interview",
) -> ValidationEvidenceEntry:
    return ValidationEvidenceEntry(
        theme="lead + follow up",
        validation_plan_path=(
            "reports/intelligence/validation_plans/"
            "lead_and_follow_up_validation_plan.md"
        ),
        evidence_type=evidence_type,
        evidence_summary="User confirmed delayed follow-up causes lost leads.",
        source_reference="Interview",
        signal_strength=signal_strength,
        supports_validation=supports_validation,
        timestamp="2026-06-08T00:00:00+00:00",
        notes="",
    )


def test_validation_evidence_summary_returns_no_evidence():
    summary = ValidationEvidenceSummarizer().summarize_entries(
        theme="lead + follow up",
        entries=[],
    )

    assert summary.status == "NO_EVIDENCE"
    assert summary.total_entries == 0


def test_validation_evidence_summary_marks_single_supporting_entry_as_early_signal():
    summary = ValidationEvidenceSummarizer().summarize_entries(
        theme="lead + follow up",
        entries=[make_entry()],
    )

    assert summary.status == "EARLY_SUPPORTING_SIGNAL"
    assert summary.total_entries == 1
    assert summary.supporting_entries == 1


def test_validation_evidence_summary_marks_ready_for_human_review():
    entries = [
        make_entry(signal_strength="strong"),
        make_entry(signal_strength="strong"),
        make_entry(signal_strength="medium"),
        make_entry(signal_strength="medium"),
        make_entry(signal_strength="weak"),
    ]

    summary = ValidationEvidenceSummarizer().summarize_entries(
        theme="lead + follow up",
        entries=entries,
    )

    assert summary.status == "READY_FOR_HUMAN_REVIEW"
    assert summary.total_entries == 5
    assert summary.supporting_entries == 5


def test_validation_evidence_summary_marks_negative_signal():
    entries = [
        make_entry(supports_validation=False, signal_strength="negative"),
        make_entry(supports_validation=False, signal_strength="negative"),
        make_entry(supports_validation=True, signal_strength="weak"),
    ]

    summary = ValidationEvidenceSummarizer().summarize_entries(
        theme="lead + follow up",
        entries=entries,
    )

    assert summary.status == "NEGATIVE_OR_WEAK_SIGNAL"
    assert summary.opposing_entries == 2


def test_validation_evidence_summary_counts_evidence_types():
    entries = [
        make_entry(evidence_type="customer_interview"),
        make_entry(evidence_type="willingness_to_pay"),
    ]

    summary = ValidationEvidenceSummarizer().summarize_entries(
        theme="lead + follow up",
        entries=entries,
    )

    assert ("customer_interview", 1) in summary.evidence_types
    assert ("willingness_to_pay", 1) in summary.evidence_types
