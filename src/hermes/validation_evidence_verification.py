from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from src.hermes.validation_evidence_log import (
    ValidationEvidenceEntry,
    ValidationEvidenceLog,
)
from src.hermes.validation_evidence_summary import (
    ValidationEvidenceSummarizer,
)


class ValidationEvidenceVerificationError(Exception):
    pass


@dataclass(frozen=True)
class EvidenceVerificationFinding:
    entry_index: int
    theme: str
    evidence_type: str
    source_trust: str
    source_reference: str
    signal_strength: str
    supports_validation: bool
    matched_markers: list[str]
    exclusion_reasons: list[str]
    evidence_summary: str
    notes: str
    recommended_action: str


@dataclass(frozen=True)
class ValidationEvidenceVerificationReport:
    theme: str
    total_entries: int
    gate_safe_entries: int
    gate_excluded_entries: int
    legacy_unverified_entries: int
    suspect_entries: int
    findings: list[EvidenceVerificationFinding]
    timestamp: str


class ValidationEvidenceVerifier:
    """
    Produces a read-only report of evidence excluded from gate-safe counts.

    It identifies placeholder/template material and historical entries without
    a declared source-trust class. It does not modify evidence, approve review,
    or approve building.
    """

    DEFAULT_OUTPUT_DIR = Path(
        "reports/intelligence/validation_evidence_verification"
    )

    def __init__(
        self,
        evidence_log: ValidationEvidenceLog | None = None,
        suspect_markers: set[str] | None = None,
    ):
        self.evidence_log = evidence_log or ValidationEvidenceLog()
        self.suspect_markers = (
            suspect_markers
            or ValidationEvidenceSummarizer.SUSPECT_EVIDENCE_MARKERS
        )

    def generate(self, *, theme: str) -> ValidationEvidenceVerificationReport:
        self._validate_required_text("theme", theme)
        entries = self.evidence_log.list_entries_for_theme(theme)
        return self.generate_for_entries(theme=theme, entries=entries)

    def generate_for_entries(
        self,
        *,
        theme: str,
        entries: list[ValidationEvidenceEntry],
    ) -> ValidationEvidenceVerificationReport:
        self._validate_required_text("theme", theme)

        findings = []

        for index, entry in enumerate(entries, start=1):
            matched_markers = ValidationEvidenceSummarizer.find_suspect_markers(
                entry,
                markers=self.suspect_markers,
            )
            exclusion_reasons = (
                ValidationEvidenceSummarizer.find_exclusion_reasons(
                    entry,
                    markers=self.suspect_markers,
                )
            )

            if not exclusion_reasons:
                continue

            findings.append(
                EvidenceVerificationFinding(
                    entry_index=index,
                    theme=entry.theme,
                    evidence_type=entry.evidence_type,
                    source_trust=entry.source_trust,
                    source_reference=entry.source_reference,
                    signal_strength=entry.signal_strength,
                    supports_validation=entry.supports_validation,
                    matched_markers=matched_markers,
                    exclusion_reasons=exclusion_reasons,
                    evidence_summary=entry.evidence_summary,
                    notes=entry.notes,
                    recommended_action=self._recommended_action(
                        exclusion_reasons
                    ),
                )
            )

        legacy_unverified_entries = sum(
            1
            for entry in entries
            if entry.source_trust == ValidationEvidenceLog.LEGACY_UNVERIFIED
        )
        suspect_entries = sum(
            1
            for entry in entries
            if ValidationEvidenceSummarizer.find_suspect_markers(
                entry,
                markers=self.suspect_markers,
            )
        )

        return ValidationEvidenceVerificationReport(
            theme=theme,
            total_entries=len(entries),
            gate_safe_entries=len(entries) - len(findings),
            gate_excluded_entries=len(findings),
            legacy_unverified_entries=legacy_unverified_entries,
            suspect_entries=suspect_entries,
            findings=findings,
            timestamp=datetime.now(UTC).isoformat(),
        )

    def format_markdown(
        self,
        report: ValidationEvidenceVerificationReport,
    ) -> str:
        lines = [
            f"# Validation Evidence Verification Report: {report.theme}",
            "",
            "## Summary",
            "",
            f"- Theme: {report.theme}",
            f"- Total Evidence Entries: {report.total_entries}",
            f"- Gate-Safe Evidence Entries: {report.gate_safe_entries}",
            f"- Gate-Excluded Evidence Entries: {report.gate_excluded_entries}",
            (
                "- Legacy Unverified Entries: "
                f"{report.legacy_unverified_entries}"
            ),
            f"- Suspect / Placeholder Entries: {report.suspect_entries}",
            f"- Timestamp: {report.timestamp}",
            "",
        ]

        if not report.findings:
            lines.extend(
                [
                    "## Findings",
                    "",
                    "No evidence is excluded by the verification rules.",
                    "",
                    "## Governance Note",
                    "",
                    (
                        "This report is read-only. It does not approve human "
                        "review, does not approve building, and does not "
                        "modify evidence."
                    ),
                    "",
                ]
            )
            return "\n".join(lines)

        lines.extend(["## Findings", ""])

        for finding in report.findings:
            lines.extend(
                [
                    f"### Finding {finding.entry_index}",
                    "",
                    f"- Evidence Type: {finding.evidence_type}",
                    f"- Source Trust: {finding.source_trust}",
                    f"- Source Reference: {finding.source_reference}",
                    f"- Signal Strength: {finding.signal_strength}",
                    f"- Supports Validation: {finding.supports_validation}",
                    (
                        "- Matched Marker(s): "
                        f"{', '.join(finding.matched_markers) or 'None'}"
                    ),
                    (
                        "- Exclusion Reason(s): "
                        f"{', '.join(finding.exclusion_reasons)}"
                    ),
                    f"- Evidence Summary: {finding.evidence_summary}",
                    f"- Notes: {finding.notes or 'None'}",
                    f"- Recommended Action: {finding.recommended_action}",
                    "",
                ]
            )

        lines.extend(
            [
                "## Governance Note",
                "",
                (
                    "This report is read-only. It does not approve human "
                    "review, does not approve building, and does not modify "
                    "evidence."
                ),
                "",
            ]
        )
        return "\n".join(lines)

    def write_markdown(
        self,
        *,
        report: ValidationEvidenceVerificationReport,
        output_path: str | Path,
    ) -> Path:
        path = Path(output_path)
        self._validate_output_path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.format_markdown(report), encoding="utf-8")
        return path

    @staticmethod
    def _recommended_action(exclusion_reasons: list[str]) -> str:
        if exclusion_reasons == [ValidationEvidenceLog.LEGACY_UNVERIFIED]:
            return (
                "This record has no source-trust classification because it "
                "predates the trust policy. Retain it as history, but do not "
                "use it as gate evidence."
            )

        if any(
            reason.startswith("suspect_marker:")
            for reason in exclusion_reasons
        ):
            return (
                "Do not use this placeholder, test, or template-like record "
                "as evidence. Retain it as history and collect a new "
                "source-classified record."
            )

        return (
            "Do not use this record for gate evidence until its source-trust "
            "classification is valid."
        )

    @staticmethod
    def _validate_required_text(field_name: str, value: str) -> None:
        if not isinstance(value, str) or not value.strip():
            raise ValidationEvidenceVerificationError(
                f"{field_name} is required"
            )

    @staticmethod
    def _validate_output_path(output_path: Path) -> None:
        resolved = output_path.resolve()
        project_root = Path.cwd().resolve()
        allowed_root = (
            project_root / "reports" / "intelligence"
        ).resolve()

        if not str(resolved).startswith(str(allowed_root)):
            raise ValidationEvidenceVerificationError(
                "Validation evidence verification report must be written "
                "inside reports/intelligence"
            )

        if resolved.suffix != ".md":
            raise ValidationEvidenceVerificationError(
                "Validation evidence verification report must be a Markdown file"
            )
