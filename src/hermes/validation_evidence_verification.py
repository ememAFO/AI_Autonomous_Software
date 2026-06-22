from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from src.hermes.validation_evidence_log import (
    ValidationEvidenceEntry,
    ValidationEvidenceLog,
)
from src.hermes.validation_evidence_summary import ValidationEvidenceSummarizer


class ValidationEvidenceVerificationError(Exception):
    pass


@dataclass(frozen=True)
class EvidenceVerificationFinding:
    entry_index: int
    theme: str
    evidence_type: str
    source_reference: str
    signal_strength: str
    supports_validation: bool
    matched_markers: list[str]
    evidence_summary: str
    notes: str
    recommended_action: str


@dataclass(frozen=True)
class ValidationEvidenceVerificationReport:
    theme: str
    total_entries: int
    gate_safe_entries: int
    suspect_entries: int
    findings: list[EvidenceVerificationFinding]
    timestamp: str


class ValidationEvidenceVerifier:
    """
    Produces a read-only report of suspect validation evidence.

    Purpose:
    - identify placeholder, test, mock, or unverified evidence
    - show which entries need replacement before human review
    - keep verification separate from evidence logging and gate execution

    This does not edit evidence.
    This does not approve human review or building.
    """

    DEFAULT_OUTPUT_DIR = Path("reports/intelligence/validation_evidence_verification")

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
            matched_markers = self._matched_markers(entry)

            if not matched_markers:
                continue

            findings.append(
                EvidenceVerificationFinding(
                    entry_index=index,
                    theme=entry.theme,
                    evidence_type=entry.evidence_type,
                    source_reference=entry.source_reference,
                    signal_strength=entry.signal_strength,
                    supports_validation=entry.supports_validation,
                    matched_markers=matched_markers,
                    evidence_summary=entry.evidence_summary,
                    notes=entry.notes,
                    recommended_action=(
                        "Replace this placeholder, test, or unverified evidence "
                        "with a real validation source before human review."
                    ),
                )
            )

        return ValidationEvidenceVerificationReport(
            theme=theme,
            total_entries=len(entries),
            gate_safe_entries=len(entries) - len(findings),
            suspect_entries=len(findings),
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
            f"- Suspect / Placeholder Entries: {report.suspect_entries}",
            f"- Timestamp: {report.timestamp}",
            "",
        ]

        if not report.findings:
            lines.extend(
                [
                    "## Findings",
                    "",
                    "No suspect validation evidence was detected.",
                    "",
                    "## Governance Note",
                    "",
                    (
                        "This report is read-only. It does not approve human review, "
                        "does not approve building, and does not modify evidence."
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
                    f"- Source Reference: {finding.source_reference}",
                    f"- Signal Strength: {finding.signal_strength}",
                    f"- Supports Validation: {finding.supports_validation}",
                    (
                        "- Matched Marker(s): "
                        f"{', '.join(finding.matched_markers)}"
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
                    "This report is read-only. It does not approve human review, "
                    "does not approve building, and does not modify evidence."
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

    def _matched_markers(self, entry: ValidationEvidenceEntry) -> list[str]:
        return ValidationEvidenceSummarizer.find_suspect_markers(
            entry,
            markers=self.suspect_markers,
        )

        return sorted(
            marker
            for marker in self.suspect_markers
            if marker in searchable_text
        )

    def _validate_required_text(self, field_name: str, value: str) -> None:
        if not isinstance(value, str) or not value.strip():
            raise ValidationEvidenceVerificationError(f"{field_name} is required")

    def _validate_output_path(self, output_path: Path) -> None:
        resolved = output_path.resolve()
        project_root = Path.cwd().resolve()
        allowed_root = (project_root / "reports" / "intelligence").resolve()

        if not str(resolved).startswith(str(allowed_root)):
            raise ValidationEvidenceVerificationError(
                "Validation evidence verification report must be written inside "
                "reports/intelligence"
            )

        if resolved.suffix != ".md":
            raise ValidationEvidenceVerificationError(
                "Validation evidence verification report must be a Markdown file"
            )
