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
    supporting_entries: int
    opposing_entries: int
    primary_entries: int
    secondary_entries: int
    risk_entries: int
    additional_entries_needed: int
    primary_entries_needed: int
    recommended_evidence_types: list[str]
    recommended_questions: list[str]
    warning: str
    recommended_next_action: str


class ValidationEvidenceGuideGenerator:
    """
    Generates a practical evidence collection guide for a validation theme.

    Purpose:
    - help collect the right validation evidence
    - keep blocked themes moving through evidence collection
    - avoid moving to human review before the ValidationGate passes

    This does not approve human review or building.
    """

    MIN_READY_ENTRIES = 5
    MIN_READY_SUPPORTING = 3
    MIN_READY_MEDIUM_OR_STRONG = 2
    MIN_PRIMARY_EVIDENCE_ENTRIES = 2

    def __init__(
        self,
        evidence_summarizer: ValidationEvidenceSummarizer | None = None,
    ):
        self.evidence_summarizer = evidence_summarizer or ValidationEvidenceSummarizer()

    def generate(self, theme: str) -> ValidationEvidenceGuide:
        summary = self.evidence_summarizer.summarize_theme(theme)

        additional_entries_needed = max(
            self.MIN_READY_ENTRIES - summary.total_entries,
            0,
        )

        primary_entries_needed = max(
            self.MIN_PRIMARY_EVIDENCE_ENTRIES - summary.primary_entries,
            0,
        )

        return ValidationEvidenceGuide(
            theme=theme,
            evidence_status=summary.status,
            total_entries=summary.total_entries,
            supporting_entries=summary.supporting_entries,
            opposing_entries=summary.opposing_entries,
            primary_entries=summary.primary_entries,
            secondary_entries=summary.secondary_entries,
            risk_entries=summary.risk_entries,
            additional_entries_needed=additional_entries_needed,
            primary_entries_needed=primary_entries_needed,
            recommended_evidence_types=self._recommended_evidence_types(summary),
            recommended_questions=self._recommended_questions(theme),
            warning=self._warning(summary),
            recommended_next_action=self._recommended_next_action(summary),
        )

    def format_markdown(self, guide: ValidationEvidenceGuide) -> str:
        return f"""# Validation Evidence Collection Guide: {guide.theme}

## Current Evidence Status
- Evidence Status: {guide.evidence_status}
- Total Entries: {guide.total_entries}
- Supporting Entries: {guide.supporting_entries}
- Opposing Entries: {guide.opposing_entries}
- Primary Entries: {guide.primary_entries}
- Secondary Entries: {guide.secondary_entries}
- Risk Entries: {guide.risk_entries}
- Additional Entries Needed Before Human Review: {guide.additional_entries_needed}
- Primary Entries Needed Before Human Review: {guide.primary_entries_needed}

## Warning

{guide.warning}

## Recommended Evidence Types To Collect Next

{self._format_list(guide.recommended_evidence_types)}

## Interview / Research Questions

{self._format_list(guide.recommended_questions)}

## Recommended Next Action

{guide.recommended_next_action}

## Governance Note

This guide does not approve human review or build planning. It only helps collect enough evidence for the ValidationGate to evaluate the theme.
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

        if (
            summary.primary_entries < self.MIN_PRIMARY_EVIDENCE_ENTRIES
            and summary.total_entries > 0
        ):
            return [
                "customer_interview",
                "willingness_to_pay",
                "landing_page_result",
                "competitor_check",
            ]

        if summary.status == "NO_EVIDENCE":
            return [
                "customer_interview",
                "manual_research",
                "competitor_check",
                "willingness_to_pay",
            ]

        if summary.status == "EARLY_SUPPORTING_SIGNAL":
            return [
                "customer_interview",
                "willingness_to_pay",
                "competitor_check",
                "landing_page_result",
            ]

        if summary.status == "NEGATIVE_OR_WEAK_SIGNAL":
            return [
                "customer_interview",
                "risk_finding",
                "competitor_check",
            ]

        if summary.status == "READY_FOR_HUMAN_REVIEW":
            return [
                "human_review_request",
            ]

        return [
            "customer_interview",
            "manual_research",
            "willingness_to_pay",
        ]

    def _recommended_questions(self, theme: str) -> list[str]:
        if theme.lower() == "lead + follow up":
            return [
                "How do you currently track new leads or enquiries?",
                "What happens when a lead is not followed up quickly?",
                "How often do warm leads go cold because of delayed follow-up?",
                "What tool or workaround do you currently use?",
                "Have you ever paid for CRM, automation, or reminder tools?",
                "Would you pay for a simple follow-up assistant if it saved lost leads?",
                "What would make this solution too risky, annoying, or unnecessary?",
                "Which channels matter most: email, SMS, WhatsApp, calls, or CRM tasks?",
            ]

        return [
            "How often does this problem happen?",
            "What do you currently do to solve it?",
            "What does the problem cost in time, money, or lost opportunities?",
            "Have you paid for a tool to solve this before?",
            "What would make you reject a new solution?",
            "What existing tools already solve part of this problem?",
        ]

    def _warning(self, summary: ValidationEvidenceSummary) -> str:
        if summary.status == "READY_FOR_HUMAN_REVIEW":
            return (
                "Evidence appears strong enough for the ValidationGate, but this still "
                "does not approve building."
            )

        if summary.status == "NEGATIVE_OR_WEAK_SIGNAL":
            return (
                "Current evidence is negative or weak. Do not move this theme forward "
                "without reviewing whether it should be rejected or revised."
            )

        if summary.total_entries == 0:
            return (
                "No validation evidence has been collected yet. This theme must remain "
                "blocked from human review."
            )

        if (
            summary.secondary_entries > 0
            and summary.primary_entries < self.MIN_PRIMARY_EVIDENCE_ENTRIES
        ):
            return (
                "Secondary evidence exists, but it cannot replace primary customer "
                "or behavioural evidence. More primary validation evidence is required."
            )

        return (
            "Current evidence is not enough for human review. More real validation "
            "evidence is required."
        )

    def _recommended_next_action(
        self,
        summary: ValidationEvidenceSummary,
    ) -> str:
        if summary.status == "READY_FOR_HUMAN_REVIEW":
            return "Run the ValidationGate and prepare a human review request if the gate passes."

        if summary.status == "NEGATIVE_OR_WEAK_SIGNAL":
            return "Collect counter-evidence and decide whether the theme should be rejected."

        if summary.primary_entries < self.MIN_PRIMARY_EVIDENCE_ENTRIES:
            return "Collect more primary validation evidence before running the gate again."

        return "Collect more real validation evidence before running the gate again."

    def _format_list(self, values: list[str]) -> str:
        if not values:
            return "- None."

        return "\n".join(f"- {value}" for value in values)

    def _validate_output_path(self, output_path: Path) -> None:
        resolved = output_path.resolve()
        project_root = Path.cwd().resolve()
        allowed_root = (project_root / "reports" / "intelligence").resolve()

        if not str(resolved).startswith(str(allowed_root)):
            raise ValueError(
                "Validation evidence guide must be written inside reports/intelligence"
            )

        if resolved.suffix != ".md":
            raise ValueError("Validation evidence guide must be a Markdown file")
