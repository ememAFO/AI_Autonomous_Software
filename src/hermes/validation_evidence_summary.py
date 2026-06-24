from collections import Counter
from dataclasses import dataclass, field

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
    primary_entries: int = 0
    secondary_entries: int = 0
    risk_entries: int = 0
    gate_safe_entries: int = 0
    gate_safe_supporting_entries: int = 0
    gate_safe_primary_entries: int = 0
    gate_safe_opposing_entries: int = 0
    gate_safe_signal_strengths: list[tuple[str, int]] = field(
        default_factory=list
    )
    source_trusts: list[tuple[str, int]] = field(default_factory=list)
    gate_excluded_entries: int = 0
    legacy_unverified_entries: int = 0
    suspect_entries: int = 0


class ValidationEvidenceSummarizer:
    """
    Summarizes validation evidence for a theme.

    Gate-safe evidence must have a trusted source class and no placeholder,
    test, or template markers. Public research can inform the validation
    decision, but only human-attested first-party evidence can satisfy the
    primary-evidence threshold for human review.

    This does not approve building.
    """

    MIN_READY_ENTRIES = 5
    MIN_READY_SUPPORTING = 3
    MIN_READY_MEDIUM_OR_STRONG = 2
    MIN_PRIMARY_EVIDENCE_ENTRIES = 2

    PRIMARY_EVIDENCE_TYPES = {
        "customer_interview",
        "willingness_to_pay",
        "landing_page_result",
        "waitlist_signup",
    }

    SECONDARY_EVIDENCE_TYPES = {
        "competitor_check",
        "manual_research",
    }

    RISK_EVIDENCE_TYPES = {
        "risk_finding",
    }

    SUSPECT_EVIDENCE_MARKERS = {
        "placeholder",
        "replace with real",
        "manual_test",
        "test evidence",
        "sample evidence",
        "fake",
        "dummy",
        "mock",
        "needs real",
        "competitor name here",
        "describe what the competitor offers",
    }

    def __init__(self, evidence_log: ValidationEvidenceLog | None = None):
        self.evidence_log = evidence_log or ValidationEvidenceLog()

    def summarize_theme(self, theme: str) -> ValidationEvidenceSummary:
        entries = self.evidence_log.list_entries_for_theme(theme)
        return self.summarize_entries(theme=theme, entries=entries)

    @classmethod
    def find_suspect_markers(
        cls,
        entry: ValidationEvidenceEntry,
        *,
        markers: set[str] | None = None,
    ) -> list[str]:
        searchable_text = cls._normalize_marker_text(
            " ".join(
                [
                    entry.evidence_summary,
                    entry.source_reference,
                    entry.notes,
                ]
            )
        )

        active_markers = markers or cls.SUSPECT_EVIDENCE_MARKERS
        matched_markers = []

        for marker in active_markers:
            normalized_marker = cls._normalize_marker_text(marker)
            if normalized_marker and normalized_marker in searchable_text:
                matched_markers.append(marker)

        return sorted(matched_markers)

    @classmethod
    def find_exclusion_reasons(
        cls,
        entry: ValidationEvidenceEntry,
        *,
        markers: set[str] | None = None,
    ) -> list[str]:
        reasons = []

        if entry.source_trust == ValidationEvidenceLog.LEGACY_UNVERIFIED:
            reasons.append(ValidationEvidenceLog.LEGACY_UNVERIFIED)
        elif entry.source_trust not in ValidationEvidenceLog.ALLOWED_SOURCE_TRUSTS:
            reasons.append("unsupported_source_trust")

        reasons.extend(
            f"suspect_marker:{marker}"
            for marker in cls.find_suspect_markers(
                entry,
                markers=markers,
            )
        )

        return reasons

    @classmethod
    def is_gate_safe(
        cls,
        entry: ValidationEvidenceEntry,
        *,
        markers: set[str] | None = None,
    ) -> bool:
        return not cls.find_exclusion_reasons(entry, markers=markers)

    @classmethod
    def is_gate_safe_primary(
        cls,
        entry: ValidationEvidenceEntry,
        *,
        markers: set[str] | None = None,
    ) -> bool:
        return (
            entry.evidence_type in cls.PRIMARY_EVIDENCE_TYPES
            and entry.source_trust
            == ValidationEvidenceLog.HUMAN_ATTESTED_FIRST_PARTY
            and cls.is_gate_safe(entry, markers=markers)
        )

    @staticmethod
    def _normalize_marker_text(value: str) -> str:
        normalized = "".join(
            character.lower() if character.isalnum() else " "
            for character in value
        )
        return " ".join(normalized.split())

    def summarize_entries(
        self,
        *,
        theme: str,
        entries: list[ValidationEvidenceEntry],
    ) -> ValidationEvidenceSummary:
        signal_counter = Counter(entry.signal_strength for entry in entries)
        evidence_type_counter = Counter(entry.evidence_type for entry in entries)
        source_trust_counter = Counter(entry.source_trust for entry in entries)

        supporting_entries = sum(
            1 for entry in entries if entry.supports_validation
        )
        opposing_entries = sum(
            1 for entry in entries if not entry.supports_validation
        )

        primary_entries = sum(
            1
            for entry in entries
            if entry.evidence_type in self.PRIMARY_EVIDENCE_TYPES
        )
        secondary_entries = sum(
            1
            for entry in entries
            if entry.evidence_type in self.SECONDARY_EVIDENCE_TYPES
        )
        risk_entries = sum(
            1
            for entry in entries
            if entry.evidence_type in self.RISK_EVIDENCE_TYPES
        )

        exclusion_reasons_by_entry = {
            index: self.find_exclusion_reasons(entry)
            for index, entry in enumerate(entries)
        }
        gate_safe_entries_list = [
            entry
            for index, entry in enumerate(entries)
            if not exclusion_reasons_by_entry[index]
        ]

        gate_safe_signal_counter = Counter(
            entry.signal_strength for entry in gate_safe_entries_list
        )
        gate_safe_supporting_entries = sum(
            1
            for entry in gate_safe_entries_list
            if entry.supports_validation
        )
        gate_safe_opposing_entries = sum(
            1
            for entry in gate_safe_entries_list
            if not entry.supports_validation
        )
        gate_safe_primary_entries = sum(
            1
            for entry in gate_safe_entries_list
            if self.is_gate_safe_primary(entry)
        )

        suspect_entries = sum(
            1
            for entry in entries
            if self.find_suspect_markers(entry)
        )
        legacy_unverified_entries = sum(
            1
            for entry in entries
            if entry.source_trust == ValidationEvidenceLog.LEGACY_UNVERIFIED
        )
        gate_excluded_entries = sum(
            1
            for reasons in exclusion_reasons_by_entry.values()
            if reasons
        )

        status = self._status(
            total_entries=len(entries),
            gate_safe_entries=len(gate_safe_entries_list),
            gate_safe_supporting_entries=gate_safe_supporting_entries,
            gate_safe_opposing_entries=gate_safe_opposing_entries,
            gate_safe_primary_entries=gate_safe_primary_entries,
            gate_safe_signal_counter=gate_safe_signal_counter,
            gate_excluded_entries=gate_excluded_entries,
        )

        return ValidationEvidenceSummary(
            theme=theme,
            total_entries=len(entries),
            supporting_entries=supporting_entries,
            opposing_entries=opposing_entries,
            signal_strengths=signal_counter.most_common(),
            evidence_types=evidence_type_counter.most_common(),
            status=status,
            recommended_next_action=self._recommended_next_action(
                status=status,
                gate_safe_primary_entries=gate_safe_primary_entries,
                gate_excluded_entries=gate_excluded_entries,
                legacy_unverified_entries=legacy_unverified_entries,
                suspect_entries=suspect_entries,
            ),
            primary_entries=primary_entries,
            secondary_entries=secondary_entries,
            risk_entries=risk_entries,
            gate_safe_entries=len(gate_safe_entries_list),
            gate_safe_supporting_entries=gate_safe_supporting_entries,
            gate_safe_primary_entries=gate_safe_primary_entries,
            gate_safe_opposing_entries=gate_safe_opposing_entries,
            gate_safe_signal_strengths=gate_safe_signal_counter.most_common(),
            source_trusts=source_trust_counter.most_common(),
            gate_excluded_entries=gate_excluded_entries,
            legacy_unverified_entries=legacy_unverified_entries,
            suspect_entries=suspect_entries,
        )

    def _status(
        self,
        *,
        total_entries: int,
        gate_safe_entries: int,
        gate_safe_supporting_entries: int,
        gate_safe_opposing_entries: int,
        gate_safe_primary_entries: int,
        gate_safe_signal_counter: Counter[str],
        gate_excluded_entries: int,
    ) -> str:
        if total_entries == 0:
            return "NO_EVIDENCE"

        if gate_safe_entries == 0 and gate_excluded_entries > 0:
            return "EVIDENCE_NEEDS_VERIFICATION"

        if gate_safe_opposing_entries > gate_safe_supporting_entries:
            return "NEGATIVE_OR_WEAK_SIGNAL"

        medium_or_strong = (
            gate_safe_signal_counter.get("strong", 0)
            + gate_safe_signal_counter.get("medium", 0)
        )

        if (
            gate_safe_entries >= self.MIN_READY_ENTRIES
            and gate_safe_supporting_entries >= self.MIN_READY_SUPPORTING
            and medium_or_strong >= self.MIN_READY_MEDIUM_OR_STRONG
            and gate_safe_primary_entries >= self.MIN_PRIMARY_EVIDENCE_ENTRIES
        ):
            return "READY_FOR_HUMAN_REVIEW"

        if gate_safe_entries >= self.MIN_READY_ENTRIES:
            if gate_safe_primary_entries < self.MIN_PRIMARY_EVIDENCE_ENTRIES:
                return "NEEDS_FIRST_PARTY_VALIDATION"
            return "NEEDS_MORE_EVIDENCE"

        if gate_safe_supporting_entries > 0:
            return "EARLY_SUPPORTING_SIGNAL"

        if gate_safe_primary_entries < self.MIN_PRIMARY_EVIDENCE_ENTRIES:
            return "NEEDS_FIRST_PARTY_VALIDATION"

        return "NEEDS_MORE_EVIDENCE"

    def _recommended_next_action(
        self,
        *,
        status: str,
        gate_safe_primary_entries: int,
        gate_excluded_entries: int,
        legacy_unverified_entries: int,
        suspect_entries: int,
    ) -> str:
        if status == "NO_EVIDENCE":
            return "Collect validation evidence before making any decision."

        if status == "READY_FOR_HUMAN_REVIEW":
            return (
                "Send validation evidence to a human reviewer. "
                "This still does not approve building."
            )

        if status == "NEGATIVE_OR_WEAK_SIGNAL":
            return (
                "Review the negative public or first-party signal, collect "
                "counter-evidence, and decide whether the theme should be "
                "revised, paused, rejected, or archived."
            )

        if status == "EVIDENCE_NEEDS_VERIFICATION":
            if suspect_entries > 0:
                return (
                    "Replace placeholder, test, or template-like evidence with "
                    "new source-classified evidence before human review."
                )
            return (
                "Current records are historical or unverified. Keep them as "
                "audit history and collect new source-classified evidence "
                "before human review."
            )

        if status == "NEEDS_FIRST_PARTY_VALIDATION":
            return (
                "Public research may inform the theme, but collect "
                "human-attested first-party evidence before human review."
            )

        if gate_safe_primary_entries < self.MIN_PRIMARY_EVIDENCE_ENTRIES:
            return (
                "Collect more human-attested first-party validation evidence "
                "before human review."
            )

        if gate_excluded_entries or legacy_unverified_entries:
            return (
                "Continue with gate-safe evidence collection. Excluded legacy "
                "records remain historical audit evidence and do not count "
                "toward the gate."
            )

        if status == "EARLY_SUPPORTING_SIGNAL":
            return "Collect more gate-safe validation evidence before human review."

        return "Continue collecting gate-safe validation evidence."
