from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from src.hermes.theme_state_registry import ThemeStateRegistry
from src.hermes.validation_evidence_summary import (
    ValidationEvidenceSummarizer,
    ValidationEvidenceSummary,
)
from src.hermes.validation_gate import ValidationGate


class ValidationProgressSnapshotError(Exception):
    pass


@dataclass(frozen=True)
class ValidationProgressSnapshot:
    theme_id: str
    theme_name: str
    current_state: str | None
    evidence_status: str
    gate_status: str
    gate_reason: str
    total_entries: int
    required_total_entries: int
    total_entries_needed: int
    supporting_entries: int
    opposing_entries: int
    primary_entries: int
    required_primary_entries: int
    primary_entries_needed: int
    secondary_entries: int
    risk_entries: int
    recommended_next_action: str
    policy_version: str
    run_id: str
    timestamp: str


class ValidationProgressSnapshotGenerator:
    """
    Builds a read-only validation progress snapshot for a theme.

    Purpose:
    - show the current validation position in one place
    - explain why a theme is blocked or ready for gate execution
    - combine theme state, evidence summary, and gate conditions
    - avoid accidental state changes

    This does not approve human review or building.
    This does not write state transitions.
    """

    REQUIRED_GATE_STATE = ValidationGate.REQUIRED_CURRENT_STATE
    REQUIRED_EVIDENCE_STATUS = ValidationGate.REQUIRED_EVIDENCE_STATUS

    MIN_READY_ENTRIES = ValidationEvidenceSummarizer.MIN_READY_ENTRIES
    MIN_READY_SUPPORTING = ValidationEvidenceSummarizer.MIN_READY_SUPPORTING
    MIN_READY_MEDIUM_OR_STRONG = (
        ValidationEvidenceSummarizer.MIN_READY_MEDIUM_OR_STRONG
    )
    MIN_PRIMARY_EVIDENCE_ENTRIES = (
        ValidationEvidenceSummarizer.MIN_PRIMARY_EVIDENCE_ENTRIES
    )

    def __init__(
        self,
        *,
        state_registry: ThemeStateRegistry | None = None,
        evidence_summarizer: ValidationEvidenceSummarizer | None = None,
    ):
        self.state_registry = state_registry or ThemeStateRegistry()
        self.evidence_summarizer = evidence_summarizer or ValidationEvidenceSummarizer()

    def generate(
        self,
        *,
        theme_id: str,
        theme_name: str,
        policy_version: str,
        run_id: str,
    ) -> ValidationProgressSnapshot:
        self._validate_required_text("theme_id", theme_id)
        self._validate_required_text("theme_name", theme_name)
        self._validate_required_text("policy_version", policy_version)
        self._validate_required_text("run_id", run_id)

        current_state = self.state_registry.get_current_state(theme_id)
        evidence_summary = self.evidence_summarizer.summarize_theme(theme_name)

        gate_status, gate_reason, recommended_next_action = self._gate_position(
            current_state=current_state,
            evidence_summary=evidence_summary,
        )

        return ValidationProgressSnapshot(
            theme_id=theme_id,
            theme_name=theme_name,
            current_state=current_state,
            evidence_status=evidence_summary.status,
            gate_status=gate_status,
            gate_reason=gate_reason,
            total_entries=evidence_summary.total_entries,
            required_total_entries=self.MIN_READY_ENTRIES,
            total_entries_needed=max(
                self.MIN_READY_ENTRIES - evidence_summary.total_entries,
                0,
            ),
            supporting_entries=evidence_summary.supporting_entries,
            opposing_entries=evidence_summary.opposing_entries,
            primary_entries=evidence_summary.primary_entries,
            required_primary_entries=self.MIN_PRIMARY_EVIDENCE_ENTRIES,
            primary_entries_needed=max(
                self.MIN_PRIMARY_EVIDENCE_ENTRIES
                - evidence_summary.primary_entries,
                0,
            ),
            secondary_entries=evidence_summary.secondary_entries,
            risk_entries=evidence_summary.risk_entries,
            recommended_next_action=recommended_next_action,
            policy_version=policy_version,
            run_id=run_id,
            timestamp=datetime.now(UTC).isoformat(),
        )

    def format_markdown(self, snapshot: ValidationProgressSnapshot) -> str:
        return f"""# Validation Progress Snapshot: {snapshot.theme_name}

## Theme

- Theme ID: {snapshot.theme_id}
- Theme Name: {snapshot.theme_name}
- Current State: {snapshot.current_state}
- Policy Version: {snapshot.policy_version}
- Run ID: {snapshot.run_id}
- Timestamp: {snapshot.timestamp}

## Evidence Position

- Evidence Status: {snapshot.evidence_status}
- Total Evidence: {snapshot.total_entries} / {snapshot.required_total_entries}
- Total Evidence Still Needed: {snapshot.total_entries_needed}
- Primary Evidence: {snapshot.primary_entries} / {snapshot.required_primary_entries}
- Primary Evidence Still Needed: {snapshot.primary_entries_needed}
- Secondary Evidence: {snapshot.secondary_entries}
- Risk Evidence: {snapshot.risk_entries}
- Supporting Entries: {snapshot.supporting_entries}
- Opposing Entries: {snapshot.opposing_entries}

## Gate Position

- Gate Status: {snapshot.gate_status}
- Gate Reason: {snapshot.gate_reason}

## Recommended Next Action

{snapshot.recommended_next_action}

## Governance Note

This snapshot is read-only. It does not approve human review, does not approve building, and does not write any state transition.
"""

    def write_markdown(
        self,
        *,
        snapshot: ValidationProgressSnapshot,
        output_path: str | Path,
    ) -> Path:
        path = Path(output_path)
        self._validate_output_path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.format_markdown(snapshot), encoding="utf-8")

        return path

    def _gate_position(
        self,
        *,
        current_state: str | None,
        evidence_summary: ValidationEvidenceSummary,
    ) -> tuple[str, str, str]:
        if current_state is None:
            return (
                "BLOCKED",
                "Theme is not registered in the theme state registry.",
                "Register the theme and move it through the validation workflow.",
            )

        if current_state != self.REQUIRED_GATE_STATE:
            return (
                "BLOCKED",
                (
                    f"Validation gate requires current state "
                    f"{self.REQUIRED_GATE_STATE}, got {current_state}."
                ),
                "Move the theme through the required validation workflow before gate review.",
            )

        if evidence_summary.status != self.REQUIRED_EVIDENCE_STATUS:
            blockers = self._evidence_blockers(evidence_summary)

            blocker_text = ""
            if blockers:
                blocker_text = " Blockers: " + "; ".join(blockers) + "."

            return (
                "BLOCKED",
                (
                    f"Validation evidence is not ready for human review: "
                    f"{evidence_summary.status}."
                    f"{blocker_text}"
                ),
                evidence_summary.recommended_next_action,
            )

        return (
            "READY_FOR_HUMAN_REVIEW",
            (
                "Snapshot indicates the validation gate conditions are met. "
                "Run the ValidationGate to record the READY_FOR_REVIEW transition."
            ),
            "Run the ValidationGate and prepare a human review request if it passes.",
        )

    def _evidence_blockers(
        self,
        evidence_summary: ValidationEvidenceSummary,
    ) -> list[str]:
        blockers = []

        if evidence_summary.total_entries < self.MIN_READY_ENTRIES:
            blockers.append(
                f"total evidence "
                f"{evidence_summary.total_entries}/{self.MIN_READY_ENTRIES}"
            )

        if evidence_summary.primary_entries < self.MIN_PRIMARY_EVIDENCE_ENTRIES:
            blockers.append(
                f"primary evidence "
                f"{evidence_summary.primary_entries}/"
                f"{self.MIN_PRIMARY_EVIDENCE_ENTRIES}"
            )

        if evidence_summary.supporting_entries < self.MIN_READY_SUPPORTING:
            blockers.append(
                f"supporting evidence "
                f"{evidence_summary.supporting_entries}/"
                f"{self.MIN_READY_SUPPORTING}"
            )

        signal_strengths = dict(evidence_summary.signal_strengths)
        medium_or_strong = (
            signal_strengths.get("strong", 0)
            + signal_strengths.get("medium", 0)
        )

        if medium_or_strong < self.MIN_READY_MEDIUM_OR_STRONG:
            blockers.append(
                f"medium-or-strong signals "
                f"{medium_or_strong}/{self.MIN_READY_MEDIUM_OR_STRONG}"
            )

        if evidence_summary.opposing_entries > evidence_summary.supporting_entries:
            blockers.append("opposing evidence exceeds supporting evidence")

        return blockers

    def _validate_required_text(self, field_name: str, value: str) -> None:
        if not isinstance(value, str) or not value.strip():
            raise ValidationProgressSnapshotError(f"{field_name} is required")

    def _validate_output_path(self, output_path: Path) -> None:
        resolved = output_path.resolve()
        project_root = Path.cwd().resolve()
        allowed_root = (project_root / "reports" / "intelligence").resolve()

        if not str(resolved).startswith(str(allowed_root)):
            raise ValidationProgressSnapshotError(
                "Validation progress snapshot must be written inside reports/intelligence"
            )

        if resolved.suffix != ".md":
            raise ValidationProgressSnapshotError(
                "Validation progress snapshot must be a Markdown file"
            )
