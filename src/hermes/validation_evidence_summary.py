from collections import Counter
from dataclasses import dataclass

from src.hermes.validation_evidence_log import (
    ValidationEvidenceEntry,
    ValidationEvidenceLog,
)


@dataclass(frozen=True)
class ValidationEvidenceSummary:
    theme: str
    total_entries: int
    supporting_entries: int
    opposing_entries: int
    signal_strengths: list[tuple[str, int]]
    evidence_types: list[tuple[str, int]]
    status: str
    recommended_next_action: str


class ValidationEvidenceSummarizer:
    """
    Summarizes validation evidence for a theme.

    Purpose:
    - evaluate whether validation evidence is strong enough for human review
    - prevent a single positive signal from becoming build approval
    - keep evidence assessment separate from MVP planning

    This does NOT approve building.
    """

    MIN_READY_ENTRIES = 5
    MIN_READY_SUPPORTING = 3
    MIN_READY_MEDIUM_OR_STRONG = 2

    def __init__(self, evidence_log: ValidationEvidenceLog | None = None):
        self.evidence_log = evidence_log or ValidationEvidenceLog()

    def summarize_theme(self, theme: str) -> ValidationEvidenceSummary:
        entries = self.evidence_log.list_entries_for_theme(theme)

        return self.summarize_entries(theme=theme, entries=entries)

    def summarize_entries(
        self,
        *,
        theme: str,
        entries: list[ValidationEvidenceEntry],
    ) -> ValidationEvidenceSummary:
        signal_counter = Counter(entry.signal_strength for entry in entries)
        evidence_type_counter = Counter(entry.evidence_type for entry in entries)

        supporting_entries = sum(
            1 for entry in entries if entry.supports_validation
        )

        opposing_entries = sum(
            1 for entry in entries if not entry.supports_validation
        )

        status = self._status(
            total_entries=len(entries),
            supporting_entries=supporting_entries,
            opposing_entries=opposing_entries,
            signal_counter=signal_counter,
        )

        return ValidationEvidenceSummary(
            theme=theme,
            total_entries=len(entries),
            supporting_entries=supporting_entries,
            opposing_entries=opposing_entries,
            signal_strengths=signal_counter.most_common(),
            evidence_types=evidence_type_counter.most_common(),
            status=status,
            recommended_next_action=self._recommended_next_action(status),
        )

    def _status(
        self,
        *,
        total_entries: int,
        supporting_entries: int,
        opposing_entries: int,
        signal_counter: Counter[str],
    ) -> str:
        if total_entries == 0:
            return "NO_EVIDENCE"

        if opposing_entries > supporting_entries:
            return "NEGATIVE_OR_WEAK_SIGNAL"

        medium_or_strong = (
            signal_counter.get("strong", 0)
            + signal_counter.get("medium", 0)
        )

        if (
            total_entries >= self.MIN_READY_ENTRIES
            and supporting_entries >= self.MIN_READY_SUPPORTING
            and medium_or_strong >= self.MIN_READY_MEDIUM_OR_STRONG
        ):
            return "READY_FOR_HUMAN_REVIEW"

        if supporting_entries > 0:
            return "EARLY_SUPPORTING_SIGNAL"

        return "NEEDS_MORE_EVIDENCE"

    def _recommended_next_action(self, status: str) -> str:
        if status == "NO_EVIDENCE":
            return "Collect validation evidence before making any decision."

        if status == "EARLY_SUPPORTING_SIGNAL":
            return "Collect more real validation evidence before human review."

        if status == "READY_FOR_HUMAN_REVIEW":
            return "Send validation evidence to a human reviewer. This still does not approve building."

        if status == "NEGATIVE_OR_WEAK_SIGNAL":
            return "Review whether the validation plan should be rejected, revised, or paused."

        return "Continue collecting validation evidence."
