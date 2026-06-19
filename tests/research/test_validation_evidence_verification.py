from pathlib import Path

import pytest

from src.hermes.validation_evidence_log import (
    ValidationEvidenceEntry,
    ValidationEvidenceLog,
)
from src.hermes.validation_evidence_verification import (
    ValidationEvidenceVerificationError,
    ValidationEvidenceVerifier,
)


THEME = "lead + follow up"


def clean_path(path: str) -> None:
    file_path = Path(path)

    if file_path.exists():
        file_path.unlink()


def make_log(
    path: str = "reports/intelligence/test_validation_evidence_verification_log.json",
) -> ValidationEvidenceLog:
    clean_path(path)
    return ValidationEvidenceLog(log_path=path)


def make_entry(
    *,
    evidence_summary: str = "User confirmed delayed follow-up causes lost leads.",
    source_reference: str = "Interview 001",
    notes: str = "",
    evidence_type: str = "customer_interview",
) -> ValidationEvidenceEntry:
    return ValidationEvidenceEntry(
        theme=THEME,
        validation_plan_path=(
            "reports/intelligence/validation_plans/"
            "lead_and_follow_up_validation_plan.md"
        ),
        evidence_type=evidence_type,
        evidence_summary=evidence_summary,
        source_reference=source_reference,
        signal_strength="strong",
        supports_validation=True,
        timestamp="2026-06-08T00:00:00+00:00",
        notes=notes,
    )


def test_validation_evidence_verifier_reports_suspect_entries():
    entries = [
        make_entry(source_reference="Interview 001"),
        make_entry(
            source_reference="manual_test_interview_002",
            notes="Primary evidence placeholder. Replace with real interview reference.",
        ),
    ]

    report = ValidationEvidenceVerifier().generate_for_entries(
        theme=THEME,
        entries=entries,
    )

    assert report.total_entries == 2
    assert report.gate_safe_entries == 1
    assert report.suspect_entries == 1

    finding = report.findings[0]

    assert finding.entry_index == 2
    assert finding.source_reference == "manual_test_interview_002"
    assert "placeholder" in finding.matched_markers
    assert "replace with real" in finding.matched_markers


def test_validation_evidence_verifier_reports_no_findings_for_clean_entries():
    entries = [
        make_entry(source_reference="Interview 001"),
        make_entry(source_reference="Interview 002"),
    ]

    report = ValidationEvidenceVerifier().generate_for_entries(
        theme=THEME,
        entries=entries,
    )

    assert report.total_entries == 2
    assert report.gate_safe_entries == 2
    assert report.suspect_entries == 0
    assert report.findings == []


def test_validation_evidence_verifier_reads_entries_from_log():
    log = make_log()

    log.add_entry(
        theme=THEME,
        validation_plan_path=(
            "reports/intelligence/validation_plans/"
            "lead_and_follow_up_validation_plan.md"
        ),
        evidence_type="willingness_to_pay",
        evidence_summary="Placeholder willingness-to-pay evidence.",
        source_reference="manual_test_wtp_001",
        signal_strength="strong",
        supports_validation=True,
        notes="Replace with real source reference.",
    )

    report = ValidationEvidenceVerifier(log).generate(theme=THEME)

    assert report.total_entries == 1
    assert report.suspect_entries == 1
    assert report.findings[0].evidence_type == "willingness_to_pay"


def test_validation_evidence_verifier_writes_markdown_report():
    report = ValidationEvidenceVerifier().generate_for_entries(
        theme=THEME,
        entries=[
            make_entry(
                source_reference="manual_test_interview_001",
                notes="Primary evidence placeholder.",
            )
        ],
    )

    output_path = Path(
        "reports/intelligence/test_validation_evidence_verification_reports/"
        "lead_follow_up_verification_report.md"
    )

    if output_path.exists():
        output_path.unlink()

    written_path = ValidationEvidenceVerifier().write_markdown(
        report=report,
        output_path=output_path,
    )

    assert written_path.exists()

    content = written_path.read_text(encoding="utf-8")
    assert "Validation Evidence Verification Report" in content
    assert "manual_test_interview_001" in content
    assert "read-only" in content


def test_validation_evidence_verifier_blocks_unsafe_output_path():
    report = ValidationEvidenceVerifier().generate_for_entries(
        theme=THEME,
        entries=[],
    )

    with pytest.raises(ValidationEvidenceVerificationError):
        ValidationEvidenceVerifier().write_markdown(
            report=report,
            output_path="../../unsafe.md",
        )


def test_validation_evidence_verifier_blocks_non_markdown_output_path():
    report = ValidationEvidenceVerifier().generate_for_entries(
        theme=THEME,
        entries=[],
    )

    with pytest.raises(ValidationEvidenceVerificationError):
        ValidationEvidenceVerifier().write_markdown(
            report=report,
            output_path="reports/intelligence/unsafe.txt",
        )
