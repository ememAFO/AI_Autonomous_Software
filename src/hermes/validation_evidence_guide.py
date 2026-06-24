from dataclasses import dataclass
from pathlib import Path

from src.hermes.validation_evidence_summary import (
    ValidationEvidenceSummarizer,
    ValidationEvidenceSummary,
)


@dataclass(frozen=True)
class ValidationEvidenceGuide:
    theme: str
    evidence_status: str
    total_entries: int
    gate_safe_entries: int
    supporting_entries: int
    opposing_entries: int
    primary_entries: int
    gate_safe_primary_entries: int
    secondary_entries: int
    risk_entries: int
    gate_excluded_entries: int
    legacy_unverified_entries: int
    additional_entries_needed: int
    primary_entries_needed: int
    recommended_evidence_types: list[str]
    recommended_questions: list[str]
    warning: str
    recommended_next_action: str


class ValidationEvidenceGuideGenerator:
    """
    Generates a practical evidence collection guide for a validation theme.

    It makes the difference between public research and human-attested
    first-party validation explicit. This does not approve review or build.
    """

    MIN_READY_ENTRIES = ValidationEvidenceSummarizer.MIN_READY_ENTRIES
    MIN_PRIMARY_EVIDENCE_ENTRIES = (
        ValidationEvidenceSummarizer.MIN_PRIMARY_EVIDENCE_ENTRIES
    )

    def __init__(
        self,
        evidence_summarizer: ValidationEvidenceSummarizer | None = None,
    ):
        self.evidence_summarizer = (
            evidence_summarizer or ValidationEvidenceSummarizer()
        )

    def generate(self, theme: str) -> ValidationEvidenceGuide:
        summary = self.evidence_summarizer.summarize_theme(theme)

        return ValidationEvidenceGuide(
            theme=theme,
            evidence_status=summary.status,
            total_entries=summary.total_entries,
            gate_safe_entries=summary.gate_safe_entries,
            supporting_entries=summary.supporting_entries,
            opposing_entries=summary.opposing_entries,
            primary_entries=summary.primary_entries,
            gate_safe_primary_entries=summary.gate_safe_primary_entries,
            secondary_entries=summary.secondary_entries,
            risk_entries=summary.risk_entries,
            gate_excluded_entries=summary.gate_excluded_entries,
            legacy_unverified_entries=(
                summary.legacy_unverified_entries
            ),
            additional_entries_needed=max(
                self.MIN_READY_ENTRIES - summary.gate_safe_entries,
                0,
            ),
            primary_entries_needed=max(
                self.MIN_PRIMARY_EVIDENCE_ENTRIES
                - summary.gate_safe_primary_entries,
                0,
            ),
            recommended_evidence_types=(
                self._recommended_evidence_types(summary)
            ),
            recommended_questions=self._recommended_questions(theme),
            warning=self._warning(summary),
            recommended_next_action=self._recommended_next_action(
                summary
            ),
        )

    def format_markdown(self, guide: ValidationEvidenceGuide) -> str:
        return f"""# Validation Evidence Collection Guide: {guide.theme}

## Current Evidence Status

- Evidence Status: {guide.evidence_status}
- Raw Entries: {guide.total_entries}
- Gate-Safe Entries: {guide.gate_safe_entries}
- Supporting Entries: {guide.supporting_entries}
- Opposing Entries: {guide.opposing_entries}
- Raw Primary-Type Entries: {guide.primary_entries}
- Gate-Safe First-Party Primary Entries: {guide.gate_safe_primary_entries}
- Secondary Entries: {guide.secondary_entries}
- Risk Entries: {guide.risk_entries}
- Gate-Excluded Entries: {guide.gate_excluded_entries}
- Legacy Unverified Entries: {guide.legacy_unverified_entries}
- Additional Gate-Safe Entries Needed Before Human Review: {guide.additional_entries_needed}
- First-Party Primary Entries Needed Before Human Review: {guide.primary_entries_needed}

## Warning

{guide.warning}

## Recommended Evidence Types To Collect Next

{self._format_list(guide.recommended_evidence_types)}

## Interview / Research Questions

{self._format_list(guide.recommended_questions)}

## Recommended Next Action

{guide.recommended_next_action}

## Governance Note

Public dataset and competitor research can improve the evidence base, but cannot satisfy the human-attested first-party threshold for the ValidationGate.
"""

    def write_markdown(
        self,
        *,
        theme: str,
        output_path: str | Path,
    ) -> Path:
        path = Path(output_path)
        self._validate_output_path(path)
        path.parent.mkdir(parents=True, exist_ok=True)

        guide = self.generate(theme)
        path.write_text(self.format_markdown(guide), encoding="utf-8")
        return path

    def _recommended_evidence_types(
        self,
        summary: ValidationEvidenceSummary,
    ) -> list[str]:
        if summary.status == "NO_EVIDENCE":
            return [
                "public_dataset:manual_research",
                "public_dataset:risk_finding",
                "public_competitor:competitor_check",
                "human_attested_first_party:customer_interview",
            ]

        if summary.status == "EVIDENCE_NEEDS_VERIFICATION":
            return [
                "public_dataset:manual_research",
                "public_dataset:risk_finding",
                "public_competitor:competitor_check",
            ]

        if summary.status == "NEEDS_FIRST_PARTY_VALIDATION":
            return [
                "human_attested_first_party:customer_interview",
                "human_attested_first_party:willingness_to_pay",
                "human_attested_first_party:landing_page_result",
                "human_attested_first_party:waitlist_signup",
            ]

        if summary.status == "NEGATIVE_OR_WEAK_SIGNAL":
            return [
                "public_dataset:manual_research",
                "public_competitor:competitor_check",
                "human_attested_first_party:customer_interview",
            ]

        if summary.status == "READY_FOR_HUMAN_REVIEW":
            return ["human_review_request"]

        return [
            "public_dataset:manual_research",
            "public_dataset:risk_finding",
            "human_attested_first_party:customer_interview",
            "human_attested_first_party:willingness_to_pay",
        ]

    @staticmethod
    def _recommended_questions(theme: str) -> list[str]:
        if theme.lower() == "lead + follow up":
            return [
                "Which enquiry sources create the most follow-up work?",
                "What currently causes leads or enquiries to be missed?",
                "Which CRM, automation, or reminder tools already solve part of this?",
                "What is difficult, expensive, or unnecessary about existing tools?",
                "Would the person change their current process, and why?",
                "What evidence would disprove the proposed narrow wedge?",
            ]

        return [
            "How often does this problem happen?",
            "What currently solves it?",
            "What would make a new solution unnecessary?",
            "Which existing tools already solve part of the problem?",
            "What evidence would disprove the opportunity?",
        ]

    def _warning(self, summary: ValidationEvidenceSummary) -> str:
        if summary.status == "READY_FOR_HUMAN_REVIEW":
            return (
                "Evidence appears strong enough for the ValidationGate, but "
                "this still does not approve building."
            )

        if summary.status == "NEEDS_FIRST_PARTY_VALIDATION":
            return (
                "Public research is useful, but only human-attested first-party "
                "evidence can satisfy the primary-evidence threshold."
            )

        if summary.status == "EVIDENCE_NEEDS_VERIFICATION":
            return (
                "Existing historical evidence is excluded because it has no "
                "trusted source class or contains template-like content. Keep "
                "it as audit history; do not use it as proof."
            )

        if summary.status == "NEGATIVE_OR_WEAK_SIGNAL":
            return (
                "Gate-safe opposing evidence outweighs supporting evidence. "
                "Do not move the theme forward without a clear counter-case."
            )

        if summary.total_entries == 0:
            return (
                "No validation evidence has been collected yet. This theme "
                "must remain blocked from human review."
            )

        return (
            "Current evidence is not enough for human review. Continue with "
            "source-classified evidence collection."
        )

    @staticmethod
    def _recommended_next_action(
        summary: ValidationEvidenceSummary,
    ) -> str:
        return summary.recommended_next_action

    @staticmethod
    def _format_list(values: list[str]) -> str:
        if not values:
            return "- None."

        return "\n".join(f"- {value}" for value in values)

    @staticmethod
    def _validate_output_path(output_path: Path) -> None:
        resolved = output_path.resolve()
        project_root = Path.cwd().resolve()
        allowed_root = (
            project_root / "reports" / "intelligence"
        ).resolve()

        if not str(resolved).startswith(str(allowed_root)):
            raise ValueError(
                "Validation evidence guide must be written inside "
                "reports/intelligence"
            )

        if resolved.suffix != ".md":
            raise ValueError(
                "Validation evidence guide must be a Markdown file"
            )
