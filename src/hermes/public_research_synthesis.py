from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from src.hermes.validation_evidence_log import (
    ValidationEvidenceEntry,
    ValidationEvidenceLog,
)
from src.hermes.validation_evidence_summary import ValidationEvidenceSummarizer


class PublicResearchSynthesisError(Exception):
    pass


@dataclass(frozen=True)
class PublicResearchSynthesis:
    theme: str
    generated_at: str
    evidence_status: str
    total_entries: int
    gate_safe_public_entries: int
    public_dataset_entries: int
    public_competitor_entries: int
    public_supporting_entries: int
    public_opposing_entries: int
    entries_outside_public_synthesis: int
    supporting_evidence: list[ValidationEvidenceEntry]
    challenging_evidence: list[ValidationEvidenceEntry]
    saturation_implication: str
    future_pilot_hypothesis: str
    research_limitations: list[str]
    pilot_questions: list[str]
    recommended_next_action: str


class PublicResearchSynthesisGenerator:
    """
    Creates a read-only synthesis of gate-safe public validation research.

    The report intentionally separates public research from human-attested
    first-party validation. It does not add evidence, change state, approve a
    validation gate, or approve product work.
    """

    DEFAULT_OUTPUT_DIR = Path("reports/intelligence/public_research_synthesis")

    PUBLIC_SOURCE_TRUSTS = {
        ValidationEvidenceLog.PUBLIC_DATASET,
        ValidationEvidenceLog.PUBLIC_COMPETITOR,
    }

    def __init__(
        self,
        *,
        evidence_log: ValidationEvidenceLog | None = None,
        evidence_summarizer: ValidationEvidenceSummarizer | None = None,
        output_dir: str | Path = DEFAULT_OUTPUT_DIR,
    ):
        if evidence_log is not None and evidence_summarizer is not None:
            raise PublicResearchSynthesisError(
                "Provide either evidence_log or evidence_summarizer, not both"
            )

        self.evidence_summarizer = (
            evidence_summarizer
            or ValidationEvidenceSummarizer(evidence_log)
        )
        self.output_dir = self._validate_output_dir(Path(output_dir))

    def build(self, *, theme: str) -> PublicResearchSynthesis:
        theme = self._validate_required_text("theme", theme)
        summary = self.evidence_summarizer.summarize_theme(theme)
        entries = self.evidence_summarizer.evidence_log.list_entries_for_theme(
            theme
        )

        gate_safe_public_entries = [
            entry
            for entry in entries
            if entry.source_trust in self.PUBLIC_SOURCE_TRUSTS
            and self.evidence_summarizer.is_gate_safe(entry)
        ]
        supporting_evidence = [
            entry
            for entry in gate_safe_public_entries
            if entry.supports_validation
        ]
        challenging_evidence = [
            entry
            for entry in gate_safe_public_entries
            if not entry.supports_validation
        ]

        return PublicResearchSynthesis(
            theme=theme,
            generated_at=datetime.now(UTC).isoformat(),
            evidence_status=summary.status,
            total_entries=len(entries),
            gate_safe_public_entries=len(gate_safe_public_entries),
            public_dataset_entries=sum(
                1
                for entry in gate_safe_public_entries
                if entry.source_trust == ValidationEvidenceLog.PUBLIC_DATASET
            ),
            public_competitor_entries=sum(
                1
                for entry in gate_safe_public_entries
                if entry.source_trust == ValidationEvidenceLog.PUBLIC_COMPETITOR
            ),
            public_supporting_entries=len(supporting_evidence),
            public_opposing_entries=len(challenging_evidence),
            entries_outside_public_synthesis=(
                len(entries) - len(gate_safe_public_entries)
            ),
            supporting_evidence=supporting_evidence,
            challenging_evidence=challenging_evidence,
            saturation_implication=self._saturation_implication(
                challenging_evidence
            ),
            future_pilot_hypothesis=self._future_pilot_hypothesis(theme),
            research_limitations=self._research_limitations(),
            pilot_questions=self._pilot_questions(theme),
            recommended_next_action=summary.recommended_next_action,
        )

    def default_output_path(self, *, theme: str) -> Path:
        theme = self._validate_required_text("theme", theme)
        return self.output_dir / (
            f"{self._slugify(theme)}_public_research_synthesis.md"
        )

    def generate(
        self,
        *,
        theme: str,
        output_path: str | Path | None = None,
    ) -> tuple[PublicResearchSynthesis, Path]:
        synthesis = self.build(theme=theme)
        target_path = output_path or self.default_output_path(theme=theme)
        written_path = self.write_markdown(
            synthesis=synthesis,
            output_path=target_path,
        )
        return synthesis, written_path

    def format_markdown(self, synthesis: PublicResearchSynthesis) -> str:
        return f"""# Public Research Synthesis: {self._inline_text(synthesis.theme)}

## Scope and Governance

- Generated At: {synthesis.generated_at}
- Validation Evidence Status: {synthesis.evidence_status}
- Raw Evidence Entries for Theme: {synthesis.total_entries}
- Gate-Safe Public Research Included: {synthesis.gate_safe_public_entries}
- Public Dataset Entries: {synthesis.public_dataset_entries}
- Public Competitor Entries: {synthesis.public_competitor_entries}
- Entries Outside This Public Research Synthesis: {synthesis.entries_outside_public_synthesis}

This report includes only gate-safe evidence classified as `public_dataset` or `public_competitor`. Historical, unverified, template-like, or first-party records are not treated as public research here.

## What Public Research Supports

{self._format_evidence(synthesis.supporting_evidence, "No supporting public research is currently included.")}

## What Public Research Challenges

{self._format_evidence(synthesis.challenging_evidence, "No challenging public research is currently included. This is an evidence gap, not proof of low risk or low competition.")}

## Existing-Tool and Saturation Implication

{synthesis.saturation_implication}

## Candidate Future Pilot Hypothesis

{synthesis.future_pilot_hypothesis}

## What Public Research Cannot Prove

{self._format_list(synthesis.research_limitations)}

## Future First-Party Pilot Questions

{self._format_list(synthesis.pilot_questions)}

## Recommended Next Action

{synthesis.recommended_next_action}

## Decision Boundary

**Public research synthesis complete; first-party pilot required.**

This report is read-only. It does not add evidence, change the theme state, approve a ValidationGate, or approve MVP planning.
"""

    def write_markdown(
        self,
        *,
        synthesis: PublicResearchSynthesis,
        output_path: str | Path,
    ) -> Path:
        path = self._validate_output_path(Path(output_path))
        path.parent.mkdir(parents=True, exist_ok=True)

        temporary_path = path.with_name(
            f".{path.name}.{uuid4().hex}.tmp"
        )

        try:
            temporary_path.write_text(
                self.format_markdown(synthesis),
                encoding="utf-8",
            )
            temporary_path.replace(path)
        finally:
            if temporary_path.exists():
                temporary_path.unlink()

        return path

    def _saturation_implication(
        self,
        challenging_evidence: list[ValidationEvidenceEntry],
    ) -> str:
        if challenging_evidence:
            return (
                "Public research contains "
                f"{len(challenging_evidence)} challenging or risk signal(s). "
                "Existing workflow and automation tools already cover parts "
                "of lead capture and follow-up, so a future pilot must prove "
                "a narrow unmet need instead of assuming that generic "
                "automation is unserved."
            )

        return (
            "No gate-safe public risk or competitor evidence is currently "
            "included. This is a research gap, not evidence that the market "
            "has no established alternatives."
        )

    @staticmethod
    def _future_pilot_hypothesis(theme: str) -> str:
        if theme.lower() == "lead + follow up":
            return (
                "For a narrowly defined small-business segment, a simpler "
                "lead-follow-up workflow may be useful only where existing "
                "automation tools are seen as too expensive, difficult to "
                "configure, or poorly matched to the current process. This is "
                "a future pilot hypothesis, not a validated product requirement."
            )

        return (
            "A future pilot should test whether a clearly defined user segment "
            "has a persistent workflow problem that existing tools do not solve "
            "well enough. This is a hypothesis, not a validated product "
            "requirement."
        )

    @staticmethod
    def _research_limitations() -> list[str]:
        return [
            "Public reviews describe general workflow experiences, not verified requirements from the future pilot segment.",
            "Public research cannot prove willingness to pay, adoption behaviour, or integration readiness for a new product.",
            "Public research cannot satisfy the human-attested first-party primary-evidence threshold required before human review.",
            "Public research does not approve building or MVP planning.",
        ]

    @staticmethod
    def _pilot_questions(theme: str) -> list[str]:
        if theme.lower() == "lead + follow up":
            return [
                "Which enquiry sources create the most follow-up work today?",
                "Where do existing CRM, automation, or reminder tools fail to fit the current process?",
                "What is difficult, expensive, or unnecessary about the existing workflow?",
                "Would the business change its process or pay to solve this, and why?",
                "What result would show that a narrower lead-follow-up tool is not worth building?",
            ]

        return [
            "How does the target user experience the problem today?",
            "Which existing tool or workaround already solves part of it?",
            "What would make a new solution unnecessary?",
            "What behaviour or willingness-to-pay signal would support the pilot?",
            "What result would show the opportunity is not worth building?",
        ]

    def _format_evidence(
        self,
        entries: list[ValidationEvidenceEntry],
        fallback: str,
    ) -> str:
        if not entries:
            return f"- {fallback}"

        blocks = []
        for entry in entries:
            direction = "supports" if entry.supports_validation else "challenges"
            blocks.append(
                "\n".join(
                    [
                        f"- Source Reference: {self._inline_text(entry.source_reference)}",
                        f"  - Direction: {direction}",
                        f"  - Source Trust: {entry.source_trust}",
                        f"  - Evidence Type: {entry.evidence_type}",
                        f"  - Signal Strength: {entry.signal_strength}",
                        f"  - Finding: {self._inline_text(entry.evidence_summary)}",
                    ]
                )
            )

        return "\n\n".join(blocks)

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
            raise PublicResearchSynthesisError(f"{field_name} is required")

        return value.strip()

    def _validate_output_dir(self, output_dir: Path) -> Path:
        resolved = output_dir.resolve()
        intelligence_root = (
            Path.cwd().resolve() / "reports" / "intelligence"
        ).resolve()

        if not self._is_within(resolved, intelligence_root):
            raise PublicResearchSynthesisError(
                "Public research synthesis must stay inside "
                "reports/intelligence"
            )

        return resolved

    def _validate_output_path(self, output_path: Path) -> Path:
        resolved = output_path.resolve()

        if not self._is_within(resolved, self.output_dir):
            raise PublicResearchSynthesisError(
                "Public research synthesis output must stay inside its "
                "configured output directory"
            )

        if resolved.suffix != ".md":
            raise PublicResearchSynthesisError(
                "Public research synthesis output must be a Markdown file"
            )

        return resolved

    @staticmethod
    def _is_within(path: Path, root: Path) -> bool:
        try:
            path.relative_to(root)
            return True
        except ValueError:
            return False
