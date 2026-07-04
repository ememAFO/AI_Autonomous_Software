from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from src.hermes.public_research_synthesis import (
    PublicResearchSynthesisGenerator,
)
from src.hermes.validation_evidence_log import ValidationEvidenceLog
from src.hermes.validation_evidence_summary import (
    ValidationEvidenceSummarizer,
)


class PilotHandoffPackError(Exception):
    pass


@dataclass(frozen=True)
class PilotHandoffPack:
    theme: str
    generated_at: str
    pilot_status: str
    evidence_status: str
    gate_safe_public_research_entries: int
    public_supporting_entries: int
    public_challenging_entries: int
    gate_safe_first_party_primary_entries: int
    entries_outside_public_research: int
    candidate_target_business_profile: list[str]
    pilot_hypothesis: str
    privacy_and_consent_boundaries: list[str]
    first_party_evidence_to_collect: list[str]
    candidate_success_criteria: list[str]
    stop_or_pause_criteria: list[str]
    recommended_next_action: str


class PilotHandoffPackGenerator:
    """
    Produces a future-ready, read-only handoff pack for a first-party pilot.

    The pack does not claim that a pilot has started, create evidence, change
    state, approve a validation gate, or approve MVP planning.
    """

    DEFAULT_OUTPUT_DIR = Path("reports/intelligence/pilot_handoff_packs")
    PILOT_STATUS = "NOT_STARTED"

    def __init__(
        self,
        *,
        evidence_log: ValidationEvidenceLog | None = None,
        evidence_summarizer: ValidationEvidenceSummarizer | None = None,
        output_dir: str | Path = DEFAULT_OUTPUT_DIR,
    ):
        if evidence_log is not None and evidence_summarizer is not None:
            raise PilotHandoffPackError(
                "Provide either evidence_log or evidence_summarizer, not both"
            )

        self.evidence_summarizer = (
            evidence_summarizer
            or ValidationEvidenceSummarizer(evidence_log)
        )
        self.public_research_synthesis = PublicResearchSynthesisGenerator(
            evidence_summarizer=self.evidence_summarizer
        )
        self.output_dir = self._validate_output_dir(Path(output_dir))

    def build(self, *, theme: str) -> PilotHandoffPack:
        theme = self._validate_required_text("theme", theme)

        evidence_summary = self.evidence_summarizer.summarize_theme(theme)
        public_research = self.public_research_synthesis.build(theme=theme)

        return PilotHandoffPack(
            theme=theme,
            generated_at=datetime.now(UTC).isoformat(),
            pilot_status=self.PILOT_STATUS,
            evidence_status=evidence_summary.status,
            gate_safe_public_research_entries=(
                public_research.gate_safe_public_entries
            ),
            public_supporting_entries=(
                public_research.public_supporting_entries
            ),
            public_challenging_entries=(
                public_research.public_opposing_entries
            ),
            gate_safe_first_party_primary_entries=(
                evidence_summary.gate_safe_primary_entries
            ),
            entries_outside_public_research=(
                public_research.entries_outside_public_synthesis
            ),
            candidate_target_business_profile=(
                self._candidate_target_business_profile(theme)
            ),
            pilot_hypothesis=self._pilot_hypothesis(theme),
            privacy_and_consent_boundaries=(
                self._privacy_and_consent_boundaries()
            ),
            first_party_evidence_to_collect=(
                self._first_party_evidence_to_collect()
            ),
            candidate_success_criteria=(
                self._candidate_success_criteria()
            ),
            stop_or_pause_criteria=self._stop_or_pause_criteria(),
            recommended_next_action=self._recommended_next_action(
                evidence_summary.status
            ),
        )

    def default_output_path(self, *, theme: str) -> Path:
        theme = self._validate_required_text("theme", theme)
        return self.output_dir / (
            f"{self._slugify(theme)}_pilot_handoff_pack.md"
        )

    def generate(
        self,
        *,
        theme: str,
        output_path: str | Path | None = None,
    ) -> tuple[PilotHandoffPack, Path]:
        pack = self.build(theme=theme)
        target_path = output_path or self.default_output_path(theme=theme)
        written_path = self.write_markdown(
            pack=pack,
            output_path=target_path,
        )
        return pack, written_path

    def format_markdown(self, pack: PilotHandoffPack) -> str:
        return f"""# Pilot Handoff Pack: {self._inline_text(pack.theme)}

## Status and Decision Boundary

- Pilot Status: {pack.pilot_status}
- Generated At: {pack.generated_at}
- Validation Evidence Status: {pack.evidence_status}
- Gate-Safe Public Research Entries: {pack.gate_safe_public_research_entries}
- Public Supporting Entries: {pack.public_supporting_entries}
- Public Challenging Entries: {pack.public_challenging_entries}
- Gate-Safe First-Party Primary Entries: {pack.gate_safe_first_party_primary_entries}
- Entries Outside Public Research: {pack.entries_outside_public_research}

**This is a future pilot handoff only. No business has been enrolled, no pilot has started, and no MVP work is approved.**

## Candidate Target Business Profile

{self._format_list(pack.candidate_target_business_profile)}

## Future Pilot Hypothesis

{pack.pilot_hypothesis}

## Privacy and Consent Boundaries

{self._format_list(pack.privacy_and_consent_boundaries)}

## Exact First-Party Evidence To Collect Later

{self._format_list(pack.first_party_evidence_to_collect)}

## Candidate Success Criteria

{self._format_list(pack.candidate_success_criteria)}

## Stop or Pause Criteria

{self._format_list(pack.stop_or_pause_criteria)}

## Recommended Next Action

{pack.recommended_next_action}

## Governance Note

This pack is read-only. It does not collect data, create evidence, change
theme state, approve the ValidationGate, approve human review, or approve
MVP planning.
"""

    def write_markdown(
        self,
        *,
        pack: PilotHandoffPack,
        output_path: str | Path,
    ) -> Path:
        path = self._validate_output_path(Path(output_path))
        path.parent.mkdir(parents=True, exist_ok=True)

        temporary_path = path.with_name(
            f".{path.name}.{uuid4().hex}.tmp"
        )

        try:
            temporary_path.write_text(
                self.format_markdown(pack),
                encoding="utf-8",
            )
            temporary_path.replace(path)
        finally:
            if temporary_path.exists():
                temporary_path.unlink()

        return path

    @staticmethod
    def _candidate_target_business_profile(theme: str) -> list[str]:
        if theme.lower() == "lead + follow up":
            return [
                "Candidate segment only: small service businesses that receive enquiries through forms, messaging, calls, or booking tools.",
                "The business owner is willing to describe its current enquiry and follow-up process without sharing customer records.",
                "The current workflow depends on manual reminders, fragmented tools, or a CRM/automation setup that may be too broad for the business.",
            ]

        return [
            "Candidate segment only: a clearly defined business group with a repeatable workflow problem.",
            "The participant is willing to describe its current process without providing personal or sensitive operational data.",
            "The pilot must identify an observable workflow constraint before proposing any product change.",
        ]

    @staticmethod
    def _pilot_hypothesis(theme: str) -> str:
        if theme.lower() == "lead + follow up":
            return (
                "A narrow small-business segment may benefit from a simpler "
                "way to prioritise and follow up enquiries only where existing "
                "CRM or automation tools are too expensive, difficult to "
                "configure, or do not fit the business's actual workflow. "
                "This is a future pilot hypothesis, not a validated requirement."
            )

        return (
            "A future pilot should test whether a clearly defined business "
            "segment has a recurring workflow problem that current tools do "
            "not solve well enough. This is a hypothesis, not a validated "
            "requirement."
        )

    @staticmethod
    def _privacy_and_consent_boundaries() -> list[str]:
        return [
            "Obtain the business owner's clear consent before collecting pilot information or observing any workflow.",
            "Do not place names, email addresses, phone numbers, customer records, raw messages, screenshots, credentials, or API keys in the repository or validation evidence log.",
            "Use anonymous participant and source references plus concise, factual summaries only.",
            "Do not connect to a business system, export customer data, or automate messages until a separate human-approved security, privacy, and integration design exists.",
            "If meaningful evidence cannot be recorded without personal or sensitive data, stop and redesign the collection approach before proceeding.",
        ]

    @staticmethod
    def _first_party_evidence_to_collect() -> list[str]:
        return [
            "Record at least two genuine human-attested first-party primary entries after real interactions, using customer_interview, willingness_to_pay, landing_page_result, or waitlist_signup.",
            "For each real interaction, capture an anonymous participant reference, the current workflow, the concrete problem or counter-signal, the existing workaround, and whether the evidence supports or challenges the theme.",
            "Use add_primary_evidence.py only after a real event has occurred; never create a placeholder, example, or reconstructed interaction.",
            "Record counter-signals honestly. A participant who says the existing CRM or automation process is sufficient is valuable opposing evidence, not a failed result to hide.",
        ]

    @staticmethod
    def _candidate_success_criteria() -> list[str]:
        return [
            "At least two source-classified first-party primary records exist and accurately reflect real interactions.",
            "At least one eligible business describes a recurring missed, delayed, or difficult enquiry-follow-up workflow that its current tools do not satisfactorily address.",
            "The first-party evidence identifies a narrow workflow wedge rather than a generic request for another CRM or broad automation platform.",
            "No consent, privacy, or security boundary is bypassed to gather the evidence.",
        ]

    @staticmethod
    def _stop_or_pause_criteria() -> list[str]:
        return [
            "Stop data collection for any participant who does not provide consent or asks not to continue.",
            "Pause if recording the evidence would require personal data, raw conversations, customer records, credentials, or unauthorised system access.",
            "Pause or revise the theme if completed first-party interactions show that existing tools already solve the workflow well enough for the target segment.",
            "Do not begin integration or MVP work merely because one participant expresses interest; the governed evidence and human-review steps still apply.",
        ]

    @staticmethod
    def _recommended_next_action(evidence_status: str) -> str:
        if evidence_status == "NEEDS_FIRST_PARTY_VALIDATION":
            return (
                "Keep the theme in validation. When a suitable business is "
                "available, use this pack to run a consented first-party "
                "pilot interaction and record only genuine evidence."
            )

        if evidence_status == "READY_FOR_HUMAN_REVIEW":
            return (
                "The evidence status is ready for human review. This handoff "
                "pack does not replace the Human Review Packet or approve "
                "MVP planning."
            )

        return (
            "Use this pack only when a real pilot is appropriate. Continue "
            "following the current validation evidence and governance state."
        )

    @staticmethod
    def _format_list(values: list[str]) -> str:
        return "\n".join(f"- {value}" for value in values)

    @staticmethod
    def _inline_text(value: str) -> str:
        return " ".join(value.replace("`", "'").split())

    @staticmethod
    def _slugify(value: str) -> str:
        return (
            value.lower()
            .replace("+", "and")
            .replace("/", "-")
            .replace(" ", "_")
            .replace("__", "_")
        )

    @staticmethod
    def _validate_required_text(field_name: str, value: object) -> str:
        if not isinstance(value, str) or not value.strip():
            raise PilotHandoffPackError(f"{field_name} is required")

        return value.strip()

    def _validate_output_dir(self, output_dir: Path) -> Path:
        resolved = output_dir.resolve()
        intelligence_root = (
            Path.cwd().resolve() / "reports" / "intelligence"
        ).resolve()

        if not self._is_within(resolved, intelligence_root):
            raise PilotHandoffPackError(
                "Pilot handoff pack must stay inside reports/intelligence"
            )

        return resolved

    def _validate_output_path(self, output_path: Path) -> Path:
        resolved = output_path.resolve()

        if not self._is_within(resolved, self.output_dir):
            raise PilotHandoffPackError(
                "Pilot handoff pack output must stay inside its configured "
                "output directory"
            )

        if resolved.suffix != ".md":
            raise PilotHandoffPackError(
                "Pilot handoff pack output must be a Markdown file"
            )

        return resolved

    @staticmethod
    def _is_within(path: Path, root: Path) -> bool:
        try:
            path.relative_to(root)
            return True
        except ValueError:
            return False
