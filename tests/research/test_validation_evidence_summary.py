from pathlib import Path

from src.hermes.validation_evidence_log import ValidationEvidenceLog

from src.hermes.validation_evidence_log import ValidationEvidenceEntry
from src.hermes.validation_evidence_summary import ValidationEvidenceSummarizer


def clean_path(path: str) -> None:
    file_path = Path(path)

    if file_path.exists():
        file_path.unlink()


def make_log(path: str) -> ValidationEvidenceLog:
    clean_path(path)
    return ValidationEvidenceLog(log_path=path)

def make_entry(
    *,
    supports_validation: bool = True,
    signal_strength: str = "strong",
    evidence_type: str = "customer_interview",
    evidence_summary: str = "User confirmed delayed follow-up causes lost leads.",
    source_reference: str = "Interview",
    notes: str = "",
    source_trust: str = ValidationEvidenceLog.HUMAN_ATTESTED_FIRST_PARTY,
) -> ValidationEvidenceEntry:
    return ValidationEvidenceEntry(
        theme="lead + follow up",
        validation_plan_path=(
            "reports/intelligence/validation_plans/"
            "lead_and_follow_up_validation_plan.md"
        ),
        evidence_type=evidence_type,
        evidence_summary=evidence_summary,
        source_reference=source_reference,
        signal_strength=signal_strength,
        supports_validation=supports_validation,
        timestamp="2026-06-08T00:00:00+00:00",
        notes=notes,
        source_trust=source_trust,
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

def test_validation_evidence_summary_does_not_pass_with_only_secondary_evidence():
    log = make_log(
        "reports/intelligence/test_validation_evidence_summary_secondary_only.json"
    )

    for index in range(5):
        log.add_entry(
            theme="lead + follow up",
            validation_plan_path=(
                "reports/intelligence/validation_plans/"
                "lead_and_follow_up_validation_plan.md"
            ),
            evidence_type="competitor_check",
            evidence_summary=f"Competitor finding {index}",
            source_reference=f"competitor_source_{index}",
            signal_strength="medium",
            supports_validation=True,
            source_trust=ValidationEvidenceLog.PUBLIC_COMPETITOR,
        )

    summary = ValidationEvidenceSummarizer(log).summarize_theme(
        "lead + follow up"
    )

    assert summary.total_entries == 5
    assert summary.secondary_entries == 5
    assert summary.primary_entries == 0
    assert summary.status != "READY_FOR_HUMAN_REVIEW"
    assert summary.status == "NEEDS_FIRST_PARTY_VALIDATION"

def test_validation_evidence_summary_can_pass_with_enough_primary_evidence():
    log = make_log(
        "reports/intelligence/test_validation_evidence_summary_primary_ready.json"
    )

    evidence_types = [
        "customer_interview",
        "customer_interview",
        "willingness_to_pay",
        "competitor_check",
        "manual_research",
    ]

    for index, evidence_type in enumerate(evidence_types):
        log.add_entry(
            theme="lead + follow up",
            validation_plan_path=(
                "reports/intelligence/validation_plans/"
                "lead_and_follow_up_validation_plan.md"
            ),
            evidence_type=evidence_type,
            evidence_summary=f"Validation finding {index}",
            source_reference=f"validation_source_{index}",
            signal_strength="strong" if index < 2 else "medium",
            supports_validation=True,
            source_trust=(
                ValidationEvidenceLog.HUMAN_ATTESTED_FIRST_PARTY
                if evidence_type in {
                    "customer_interview",
                    "willingness_to_pay",
                }
                else ValidationEvidenceLog.PUBLIC_COMPETITOR
                if evidence_type == "competitor_check"
                else ValidationEvidenceLog.PUBLIC_DATASET
            ),
        )

    summary = ValidationEvidenceSummarizer(log).summarize_theme(
        "lead + follow up"
    )

    assert summary.total_entries == 5
    assert summary.primary_entries == 3
    assert summary.secondary_entries == 2
    assert summary.status == "READY_FOR_HUMAN_REVIEW"

def test_validation_evidence_summary_blocks_placeholder_evidence_from_readiness():
    entries = [
        make_entry(
            evidence_summary=f"Placeholder customer interview {index}",
            source_reference=f"manual_test_interview_{index}",
            notes="Primary evidence placeholder. Replace with real interview reference.",
        )
        for index in range(5)
    ]

    summary = ValidationEvidenceSummarizer().summarize_entries(
        theme="lead + follow up",
        entries=entries,
    )

    assert summary.total_entries == 5
    assert summary.suspect_entries == 5
    assert summary.gate_safe_entries == 0
    assert summary.gate_safe_primary_entries == 0
    assert summary.status == "EVIDENCE_NEEDS_VERIFICATION"
    assert "Replace placeholder" in summary.recommended_next_action


def test_validation_evidence_summary_blocks_normalized_template_markers():
    entries = [
        make_entry(
            evidence_summary=(
                "Participant/Signal: small_business_owner_003. "
                "Finding: REPLACE_WITH_REAL_FINDING"
            ),
            source_reference="interview_003",
        ),
        make_entry(
            evidence_type="competitor_check",
            evidence_summary=(
                "Competitor: COMPETITOR_NAME_HERE. Finding: "
                "Describe what the competitor offers, where it is too broad, "
                "too expensive, or too complex for small businesses."
            ),
            source_reference="competitor_review_001",
        ),
    ]

    summary = ValidationEvidenceSummarizer().summarize_entries(
        theme="lead + follow up",
        entries=entries,
    )

    assert summary.total_entries == 2
    assert summary.suspect_entries == 2
    assert summary.gate_safe_entries == 0
    assert summary.status == "EVIDENCE_NEEDS_VERIFICATION"





def test_validation_evidence_summary_can_pass_with_enough_gate_safe_evidence():
    real_entries = [
        make_entry(source_reference=f"Interview {index}")
        for index in range(5)
    ]

    placeholder_entry = make_entry(
        source_reference="manual_test_interview_extra",
        notes="Primary evidence placeholder. Replace with real interview reference.",
    )

    summary = ValidationEvidenceSummarizer().summarize_entries(
        theme="lead + follow up",
        entries=[*real_entries, placeholder_entry],
    )

    assert summary.total_entries == 6
    assert summary.suspect_entries == 1
    assert summary.gate_safe_entries == 5
    assert summary.gate_safe_primary_entries == 5
    assert summary.status == "READY_FOR_HUMAN_REVIEW"


def test_validation_evidence_summary_excludes_legacy_unverified_history():
    summary = ValidationEvidenceSummarizer().summarize_entries(
        theme="lead + follow up",
        entries=[
            make_entry(
                source_trust=ValidationEvidenceLog.LEGACY_UNVERIFIED
            )
        ],
    )

    assert summary.status == "EVIDENCE_NEEDS_VERIFICATION"
    assert summary.total_entries == 1
    assert summary.gate_safe_entries == 0
    assert summary.gate_excluded_entries == 1
    assert summary.legacy_unverified_entries == 1


def test_validation_evidence_summary_counts_public_dataset_but_not_primary():
    entries = [
        make_entry(
            evidence_type="manual_research",
            source_trust=ValidationEvidenceLog.PUBLIC_DATASET,
        ),
        make_entry(
            evidence_type="manual_research",
            source_trust=ValidationEvidenceLog.PUBLIC_DATASET,
        ),
    ]

    summary = ValidationEvidenceSummarizer().summarize_entries(
        theme="lead + follow up",
        entries=entries,
    )

    assert summary.gate_safe_entries == 2
    assert summary.gate_safe_primary_entries == 0
    assert summary.status == "EARLY_SUPPORTING_SIGNAL"
