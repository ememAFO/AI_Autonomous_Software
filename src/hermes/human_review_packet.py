import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from src.hermes.theme_state_registry import (
    ThemeStateEvent,
    ThemeStateRegistry,
    ThemeStateRegistryError,
)
from src.hermes.theme_validation_plan_registry import (
    ThemeValidationPlanRegistry,
    ThemeValidationPlanRegistryEntry,
    ThemeValidationPlanRegistryError,
)
from src.hermes.validation_evidence_log import (
    ValidationEvidenceEntry,
    ValidationEvidenceLog,
    ValidationEvidenceLogError,
)
from src.hermes.validation_evidence_summary import (
    ValidationEvidenceSummary,
    ValidationEvidenceSummarizer,
)
from src.hermes.validation_evidence_verification import (
    EvidenceVerificationFinding,
    ValidationEvidenceVerifier,
)
from src.utils.path_normalizer import PathNormalizerError, ProjectPathNormalizer


class HumanReviewPacketError(Exception):
    pass


class HumanReviewPacketRegistryError(Exception):
    pass


@dataclass(frozen=True)
class HumanReviewPacket:
    packet_id: str
    theme_id: str
    theme_name: str
    current_state: str
    review_status: str
    validation_plan_path: str
    validation_plan_status: str
    validation_plan_timestamp: str
    gate_event_id: str
    gate_run_id: str
    gate_policy_version: str
    state_history: list[ThemeStateEvent]
    evidence_summary: ValidationEvidenceSummary
    gate_safe_evidence: list[ValidationEvidenceEntry]
    excluded_evidence: list[EvidenceVerificationFinding]
    risk_evidence: list[ValidationEvidenceEntry]
    opposing_evidence: list[ValidationEvidenceEntry]
    reasons_not_to_build: list[str]
    policy_version: str
    run_id: str
    timestamp: str


@dataclass(frozen=True)
class HumanReviewPacketRegistryEntry:
    packet_id: str
    theme_id: str
    theme_name: str
    current_state: str
    review_status: str
    validation_plan_path: str
    gate_event_id: str
    evidence_status: str
    gate_safe_entries: int
    suspect_entries: int
    output_path: str
    policy_version: str
    run_id: str
    timestamp: str


class HumanReviewPacketGenerator:
    """
    Builds a read-only packet for human review after validation succeeds.

    This does not approve controlled MVP planning.
    This does not change theme state.
    This does not add, remove, or modify validation evidence.
    """

    DEFAULT_OUTPUT_DIR = Path("reports/intelligence/human_review_packets")

    REQUIRED_STATE = "READY_FOR_REVIEW"
    REQUIRED_EVIDENCE_STATUS = "READY_FOR_HUMAN_REVIEW"
    REQUIRED_GATE_TRIGGER = "validation_gate_passed"
    REQUIRED_GATE_ACTOR = "ValidationGate"
    REVIEW_STATUS = "PENDING_HUMAN_DECISION"

    def __init__(
        self,
        *,
        state_registry: ThemeStateRegistry | None = None,
        validation_plan_registry: ThemeValidationPlanRegistry | None = None,
        evidence_log: ValidationEvidenceLog | None = None,
        output_dir: str | Path = DEFAULT_OUTPUT_DIR,
    ):
        self.project_root = Path.cwd().resolve()
        self.intelligence_root = (
            self.project_root / "reports" / "intelligence"
        ).resolve()

        self.state_registry = state_registry or ThemeStateRegistry()
        self.validation_plan_registry = (
            validation_plan_registry or ThemeValidationPlanRegistry()
        )
        self.evidence_log = evidence_log or ValidationEvidenceLog()

        self.evidence_summarizer = ValidationEvidenceSummarizer(
            self.evidence_log
        )
        self.evidence_verifier = ValidationEvidenceVerifier(
            self.evidence_log
        )
        self.path_normalizer = ProjectPathNormalizer()

        self.output_dir = self._validate_output_dir(Path(output_dir))
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def generate(
        self,
        *,
        theme_id: str,
        theme_name: str,
        policy_version: str,
        run_id: str,
    ) -> HumanReviewPacket:
        self._validate_required_text("theme_id", theme_id)
        self._validate_required_text("theme_name", theme_name)
        self._validate_required_text("policy_version", policy_version)
        self._validate_required_text("run_id", run_id)

        try:
            self.state_registry.verify_integrity()
            state_history = self.state_registry.list_events_for_theme(theme_id)
        except ThemeStateRegistryError as exc:
            raise HumanReviewPacketError(
                "Theme state registry integrity could not be verified"
            ) from exc

        if not state_history:
            raise HumanReviewPacketError(
                f"Theme is not registered in the state registry: {theme_id}"
            )

        latest_event = state_history[-1]

        if latest_event.theme_name != theme_name:
            raise HumanReviewPacketError(
                "Theme name does not match the registered state history"
            )

        if latest_event.new_state != self.REQUIRED_STATE:
            raise HumanReviewPacketError(
                f"Human review packet requires state {self.REQUIRED_STATE}, "
                f"got {latest_event.new_state}"
            )

        if latest_event.trigger != self.REQUIRED_GATE_TRIGGER:
            raise HumanReviewPacketError(
                "READY_FOR_REVIEW must be reached through validation_gate_passed"
            )

        if latest_event.changed_by != self.REQUIRED_GATE_ACTOR:
            raise HumanReviewPacketError(
                "READY_FOR_REVIEW must be recorded by ValidationGate"
            )

        if latest_event.policy_version != policy_version:
            raise HumanReviewPacketError(
                "Requested policy version does not match the validation gate event"
            )

        evidence_summary = self.evidence_summarizer.summarize_theme(theme_name)

        if evidence_summary.status != self.REQUIRED_EVIDENCE_STATUS:
            raise HumanReviewPacketError(
                "Human review packet requires validation evidence status "
                f"{self.REQUIRED_EVIDENCE_STATUS}, got {evidence_summary.status}"
            )

        entries = self.evidence_log.list_entries_for_theme(theme_name)

        verification_report = self.evidence_verifier.generate_for_entries(
            theme=theme_name,
            entries=entries,
        )

        excluded_indexes = {
            finding.entry_index
            for finding in verification_report.findings
        }

        gate_safe_evidence = [
            entry
            for index, entry in enumerate(entries, start=1)
            if index not in excluded_indexes
        ]

        selected_plan, registered_plan_paths = (
            self._select_registered_validation_plan(theme_name)
        )

        self._validate_evidence_plan_provenance(
            entries=entries,
            registered_plan_paths=registered_plan_paths,
        )

        selected_plan_path = self._resolve_intelligence_markdown_path(
            selected_plan.output_path,
            label="Registered validation plan",
        )

        normalized_plan_path = self._normalize_project_path(selected_plan_path)

        risk_evidence = [
            entry
            for entry in entries
            if entry.evidence_type == "risk_finding"
        ]

        opposing_evidence = [
            entry
            for entry in entries
            if not entry.supports_validation
        ]

        reasons_not_to_build = self._reasons_not_to_build(
            validation_plan_path=normalized_plan_path,
            evidence_summary=evidence_summary,
            excluded_evidence=verification_report.findings,
            risk_evidence=risk_evidence,
            opposing_evidence=opposing_evidence,
        )

        return HumanReviewPacket(
            packet_id=f"human_review_packet_{uuid4().hex}",
            theme_id=theme_id,
            theme_name=theme_name,
            current_state=latest_event.new_state,
            review_status=self.REVIEW_STATUS,
            validation_plan_path=normalized_plan_path,
            validation_plan_status=selected_plan.status,
            validation_plan_timestamp=selected_plan.timestamp,
            gate_event_id=latest_event.event_id,
            gate_run_id=latest_event.run_id,
            gate_policy_version=latest_event.policy_version,
            state_history=state_history,
            evidence_summary=evidence_summary,
            gate_safe_evidence=gate_safe_evidence,
            excluded_evidence=verification_report.findings,
            risk_evidence=risk_evidence,
            opposing_evidence=opposing_evidence,
            reasons_not_to_build=reasons_not_to_build,
            policy_version=policy_version,
            run_id=run_id,
            timestamp=datetime.now(UTC).isoformat(),
        )

    def default_output_path(self, packet: HumanReviewPacket) -> Path:
        timestamp_token = "".join(
            character
            for character in packet.timestamp
            if character.isalnum()
        )

        return (
            self.output_dir
            / (
                f"{self._slugify(packet.theme_name)}_"
                f"{timestamp_token}_human_review_packet.md"
            )
        )

    def format_markdown(self, packet: HumanReviewPacket) -> str:
        lines = [
            f"# Human Review Packet: {packet.theme_name}",
            "",
            "## Review Identity",
            "",
            f"- Packet ID: {packet.packet_id}",
            f"- Theme ID: {packet.theme_id}",
            f"- Theme Name: {packet.theme_name}",
            f"- Current State: {packet.current_state}",
            f"- Review Status: {packet.review_status}",
            f"- Policy Version: {packet.policy_version}",
            f"- Packet Run ID: {packet.run_id}",
            f"- Timestamp: {packet.timestamp}",
            "",
            "## Validation Plan Provenance",
            "",
            f"- Registered Validation Plan: `{packet.validation_plan_path}`",
            f"- Plan Registry Status: {packet.validation_plan_status}",
            f"- Plan Registry Timestamp: {packet.validation_plan_timestamp}",
            "",
            "## Validation Gate Provenance",
            "",
            f"- Gate Event ID: {packet.gate_event_id}",
            f"- Gate Run ID: {packet.gate_run_id}",
            f"- Gate Policy Version: {packet.gate_policy_version}",
            "",
            "## State History",
            "",
        ]

        lines.extend(self._format_state_history(packet.state_history))

        lines.extend(
            [
                "",
                "## Evidence Position",
                "",
                f"- Evidence Status: {packet.evidence_summary.status}",
                (
                    "- Raw Evidence Entries: "
                    f"{packet.evidence_summary.total_entries}"
                ),
                (
                    "- Gate-Safe Evidence Entries: "
                    f"{packet.evidence_summary.gate_safe_entries}"
                ),
                (
                    "- Excluded / Suspect Evidence Entries: "
                    f"{packet.evidence_summary.suspect_entries}"
                ),
                (
                    "- Gate-Safe Primary Evidence: "
                    f"{packet.evidence_summary.gate_safe_primary_entries}"
                ),
                (
                    "- Gate-Safe Supporting Evidence: "
                    f"{packet.evidence_summary.gate_safe_supporting_entries}"
                ),
                (
                    "- Opposing Evidence Entries: "
                    f"{packet.evidence_summary.opposing_entries}"
                ),
                "",
                "## Gate-Safe Evidence",
                "",
            ]
        )

        lines.extend(self._format_evidence_entries(packet.gate_safe_evidence))

        lines.extend(
            [
                "",
                "## Excluded / Suspect Evidence",
                "",
            ]
        )

        lines.extend(
            self._format_excluded_evidence(packet.excluded_evidence)
        )

        lines.extend(
            [
                "",
                "## Risks, Gaps, and Contradictions",
                "",
                "### Risk Evidence",
                "",
            ]
        )

        lines.extend(self._format_evidence_entries(packet.risk_evidence))

        lines.extend(
            [
                "",
                "### Opposing Evidence",
                "",
            ]
        )

        lines.extend(self._format_evidence_entries(packet.opposing_evidence))

        lines.extend(
            [
                "",
                "## Reasons Not To Build Yet",
                "",
            ]
        )

        lines.extend(
            f"- {reason}"
            for reason in packet.reasons_not_to_build
        )

        lines.extend(
            [
                "",
                "## Human Decision Record",
                "",
                "- [ ] Approve controlled MVP planning",
                "- [ ] Return theme to validation",
                "- [ ] Reject or archive the opportunity",
                "",
                "- Reviewer:",
                "- Decision Date:",
                "- Decision Rationale:",
                "",
                "## Governance Note",
                "",
                (
                    "This packet is read-only preparation for a human decision. "
                    "Generating or registering it does not approve building, "
                    "does not change theme state, and does not modify evidence."
                ),
                "",
            ]
        )

        return "\n".join(lines)

    def write_markdown(
        self,
        *,
        packet: HumanReviewPacket,
        output_path: str | Path,
    ) -> Path:
        resolved_path = self._validate_output_path(Path(output_path))

        if resolved_path.exists():
            raise HumanReviewPacketError(
                "Human review packet output already exists and cannot be overwritten"
            )

        temporary_path = resolved_path.with_suffix(
            f"{resolved_path.suffix}.tmp"
        )

        try:
            temporary_path.write_text(
                self.format_markdown(packet),
                encoding="utf-8",
            )
            temporary_path.replace(resolved_path)
        except OSError as exc:
            raise HumanReviewPacketError(
                "Human review packet could not be written"
            ) from exc
        finally:
            if temporary_path.exists():
                temporary_path.unlink()

        return resolved_path

    def _select_registered_validation_plan(
        self,
        theme_name: str,
    ) -> tuple[ThemeValidationPlanRegistryEntry, set[str]]:
        try:
            matching_entries = [
                entry
                for entry in self.validation_plan_registry.list_entries()
                if entry.theme.lower() == theme_name.lower()
            ]
        except ThemeValidationPlanRegistryError as exc:
            raise HumanReviewPacketError(
                "Validation plan registry could not be read"
            ) from exc

        if not matching_entries:
            raise HumanReviewPacketError(
                "No registered validation plan exists for this theme"
            )

        selected_plan = matching_entries[-1]

        if selected_plan.readiness != "VALIDATION_READY":
            raise HumanReviewPacketError(
                "Registered validation plan does not have VALIDATION_READY provenance"
            )

        registered_plan_paths = {
            str(
                self._resolve_intelligence_markdown_path(
                    entry.output_path,
                    label="Registered validation plan",
                )
            )
            for entry in matching_entries
        }

        return selected_plan, registered_plan_paths

    def _validate_evidence_plan_provenance(
        self,
        *,
        entries: list[ValidationEvidenceEntry],
        registered_plan_paths: set[str],
    ) -> None:
        for entry in entries:
            evidence_plan_path = self._resolve_intelligence_markdown_path(
                entry.validation_plan_path,
                label="Validation evidence plan reference",
            )

            if str(evidence_plan_path) not in registered_plan_paths:
                raise HumanReviewPacketError(
                    "Validation evidence references a plan path that is not "
                    "registered for this theme"
                )

    def _reasons_not_to_build(
        self,
        *,
        validation_plan_path: str,
        evidence_summary: ValidationEvidenceSummary,
        excluded_evidence: list[EvidenceVerificationFinding],
        risk_evidence: list[ValidationEvidenceEntry],
        opposing_evidence: list[ValidationEvidenceEntry],
    ) -> list[str]:
        reasons = [
            (
                "No human decision has been recorded. READY_FOR_REVIEW is a "
                "review state, not approval for build work."
            ),
            (
                "The evidence threshold qualifies this theme for review only. "
                "It does not prove product-market fit, technical feasibility, "
                "pricing viability, or compliance readiness."
            ),
            (
                "Review the registered validation plan and its failure criteria "
                f"before any controlled MVP-planning decision: {validation_plan_path}"
            ),
        ]

        if not risk_evidence:
            reasons.append(
                "No risk_finding evidence is recorded. Treat this as a missing "
                "risk check, not proof that no risks exist."
            )

        if not opposing_evidence:
            reasons.append(
                "No opposing evidence is recorded. Actively challenge the "
                "opportunity during human review rather than treating silence "
                "as confirmation."
            )

        if excluded_evidence:
            reasons.append(
                f"{len(excluded_evidence)} suspect or placeholder evidence "
                "entries were excluded from gate-safe counts and must not be "
                "used as supporting proof."
            )

        if evidence_summary.suspect_entries != len(excluded_evidence):
            reasons.append(
                "Evidence-verification counts require manual review because "
                "the packet and summary disagree."
            )

        return reasons

    def _format_state_history(
        self,
        state_history: list[ThemeStateEvent],
    ) -> list[str]:
        lines = []

        for index, event in enumerate(state_history, start=1):
            previous_state = event.previous_state or "None"

            lines.extend(
                [
                    (
                        f"{index}. {previous_state} → {event.new_state} "
                        f"at {event.timestamp}"
                    ),
                    f"   - Trigger: {self._single_line(event.trigger)}",
                    f"   - Changed By: {self._single_line(event.changed_by)}",
                    (
                        "   - Related Artifact: "
                        f"{self._single_line(event.related_artifact_id)}"
                    ),
                    f"   - Run ID: {self._single_line(event.run_id)}",
                    f"   - Reason: {self._single_line(event.reason)}",
                ]
            )

        return lines or ["- No state history recorded."]

    def _format_evidence_entries(
        self,
        entries: list[ValidationEvidenceEntry],
    ) -> list[str]:
        if not entries:
            return [
                (
                    "- None recorded. Absence of entries does not prove the "
                    "absence of risk or contradiction."
                )
            ]

        lines = []

        for index, entry in enumerate(entries, start=1):
            lines.extend(
                [
                    (
                        f"{index}. {entry.evidence_type} | "
                        f"{entry.signal_strength} | "
                        f"supports_validation={entry.supports_validation}"
                    ),
                    (
                        "   - Source Reference: "
                        f"{self._single_line(entry.source_reference)}"
                    ),
                    (
                        "   - Validation Plan: "
                        f"`{self._single_line(entry.validation_plan_path)}`"
                    ),
                    (
                        "   - Summary: "
                        f"{self._single_line(entry.evidence_summary)}"
                    ),
                    f"   - Notes: {self._single_line(entry.notes) or 'None'}",
                    f"   - Timestamp: {entry.timestamp}",
                ]
            )

        return lines

    def _format_excluded_evidence(
        self,
        findings: list[EvidenceVerificationFinding],
    ) -> list[str]:
        if not findings:
            return [
                "- No suspect evidence was detected by the verification rules."
            ]

        lines = []

        for finding in findings:
            lines.extend(
                [
                    (
                        f"{finding.entry_index}. {finding.evidence_type} | "
                        f"{finding.signal_strength} | "
                        f"supports_validation={finding.supports_validation}"
                    ),
                    (
                        "   - Source Reference: "
                        f"{self._single_line(finding.source_reference)}"
                    ),
                    (
                        "   - Matched Markers: "
                        f"{', '.join(finding.matched_markers)}"
                    ),
                    (
                        "   - Summary: "
                        f"{self._single_line(finding.evidence_summary)}"
                    ),
                    (
                        "   - Notes: "
                        f"{self._single_line(finding.notes) or 'None'}"
                    ),
                    (
                        "   - Exclusion Reason: "
                        f"{self._single_line(finding.recommended_action)}"
                    ),
                ]
            )

        return lines

    def _resolve_intelligence_markdown_path(
        self,
        value: str,
        *,
        label: str,
    ) -> Path:
        self._validate_required_text(label, value)

        candidate = Path(value)

        if candidate.is_absolute():
            resolved = candidate.resolve()
        else:
            resolved = (self.project_root / candidate).resolve()

        if not self._is_within(resolved, self.intelligence_root):
            raise HumanReviewPacketError(
                f"{label} must stay inside reports/intelligence"
            )

        if resolved.suffix != ".md":
            raise HumanReviewPacketError(
                f"{label} must be a Markdown file"
            )

        if not resolved.is_file():
            raise HumanReviewPacketError(
                f"{label} does not exist: {self._normalize_project_path(resolved)}"
            )

        return resolved

    def _validate_output_dir(self, output_dir: Path) -> Path:
        resolved = output_dir.resolve()

        if not self._is_within(resolved, self.intelligence_root):
            raise HumanReviewPacketError(
                "Human review packets must stay inside reports/intelligence"
            )

        return resolved

    def _validate_output_path(self, output_path: Path) -> Path:
        if output_path.is_absolute():
            resolved = output_path.resolve()
        else:
            resolved = (self.project_root / output_path).resolve()

        if not self._is_within(resolved, self.output_dir):
            raise HumanReviewPacketError(
                "Human review packet must be written inside its approved output directory"
            )

        if resolved.suffix != ".md":
            raise HumanReviewPacketError(
                "Human review packet must be a Markdown file"
            )

        return resolved

    def _normalize_project_path(self, path: Path) -> str:
        try:
            return self.path_normalizer.normalize(str(path))
        except PathNormalizerError as exc:
            raise HumanReviewPacketError(
                "Project path could not be safely normalized"
            ) from exc

    @staticmethod
    def _is_within(path: Path, root: Path) -> bool:
        try:
            path.relative_to(root)
            return True
        except ValueError:
            return False

    @staticmethod
    def _single_line(value: str) -> str:
        return " ".join(value.split())

    @staticmethod
    def _slugify(value: str) -> str:
        slug = "".join(
            character.lower()
            if character.isalnum()
            else "_"
            for character in value
        )

        return "_".join(part for part in slug.split("_") if part)

    @staticmethod
    def _validate_required_text(field_name: str, value: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise HumanReviewPacketError(f"{field_name} is required")

        return value.strip()


class HumanReviewPacketRegistry:
    """
    Append-only index for generated human review packets.

    Registering a packet preserves output provenance only.
    It does not record a human decision or change theme state.
    """

    DEFAULT_REGISTRY_PATH = Path(
        "reports/intelligence/human_review_packet_index.json"
    )
    DEFAULT_PACKET_OUTPUT_DIR = HumanReviewPacketGenerator.DEFAULT_OUTPUT_DIR

    def __init__(
        self,
        registry_path: str | Path = DEFAULT_REGISTRY_PATH,
        packet_output_dir: str | Path = DEFAULT_PACKET_OUTPUT_DIR,
    ):
        self.project_root = Path.cwd().resolve()
        self.intelligence_root = (
            self.project_root / "reports" / "intelligence"
        ).resolve()
        self.path_normalizer = ProjectPathNormalizer()

        self.registry_path = self._validate_registry_path(Path(registry_path))
        self.packet_output_dir = self._validate_packet_output_dir(
            Path(packet_output_dir)
        )

        self.registry_path.parent.mkdir(parents=True, exist_ok=True)

    def add_packet(
        self,
        *,
        packet: HumanReviewPacket,
        output_path: str | Path,
    ) -> HumanReviewPacketRegistryEntry:
        if packet.current_state != "READY_FOR_REVIEW":
            raise HumanReviewPacketRegistryError(
                "Only READY_FOR_REVIEW packets can be registered"
            )

        if packet.evidence_summary.status != "READY_FOR_HUMAN_REVIEW":
            raise HumanReviewPacketRegistryError(
                "Only human-review-ready evidence packets can be registered"
            )

        resolved_output_path = self._validate_packet_output_path(
            Path(output_path)
        )

        if not resolved_output_path.is_file():
            raise HumanReviewPacketRegistryError(
                "Human review packet output does not exist"
            )

        entry = HumanReviewPacketRegistryEntry(
            packet_id=packet.packet_id,
            theme_id=packet.theme_id,
            theme_name=packet.theme_name,
            current_state=packet.current_state,
            review_status=packet.review_status,
            validation_plan_path=packet.validation_plan_path,
            gate_event_id=packet.gate_event_id,
            evidence_status=packet.evidence_summary.status,
            gate_safe_entries=packet.evidence_summary.gate_safe_entries,
            suspect_entries=packet.evidence_summary.suspect_entries,
            output_path=self._normalize_project_path(resolved_output_path),
            policy_version=packet.policy_version,
            run_id=packet.run_id,
            timestamp=datetime.now(UTC).isoformat(),
        )

        data = self._load_registry()
        data["packets"].append(asdict(entry))
        self._write_registry(data)

        return entry

    def list_entries(self) -> list[HumanReviewPacketRegistryEntry]:
        data = self._load_registry()

        return [
            HumanReviewPacketRegistryEntry(
                packet_id=str(item["packet_id"]),
                theme_id=str(item["theme_id"]),
                theme_name=str(item["theme_name"]),
                current_state=str(item["current_state"]),
                review_status=str(item["review_status"]),
                validation_plan_path=str(item["validation_plan_path"]),
                gate_event_id=str(item["gate_event_id"]),
                evidence_status=str(item["evidence_status"]),
                gate_safe_entries=int(item["gate_safe_entries"]),
                suspect_entries=int(item["suspect_entries"]),
                output_path=str(item["output_path"]),
                policy_version=str(item["policy_version"]),
                run_id=str(item["run_id"]),
                timestamp=str(item["timestamp"]),
            )
            for item in data["packets"]
        ]

    def _load_registry(self) -> dict:
        if not self.registry_path.exists():
            return {"packets": []}

        try:
            data = json.loads(
                self.registry_path.read_text(encoding="utf-8")
            )
        except json.JSONDecodeError as exc:
            raise HumanReviewPacketRegistryError(
                "Human review packet registry contains invalid JSON"
            ) from exc

        if not isinstance(data, dict):
            raise HumanReviewPacketRegistryError(
                "Human review packet registry must contain a JSON object"
            )

        if "packets" not in data:
            data["packets"] = []

        if not isinstance(data["packets"], list):
            raise HumanReviewPacketRegistryError(
                "Human review packet registry 'packets' field must be a list"
            )

        return data

    def _write_registry(self, data: dict) -> None:
        temporary_path = self.registry_path.with_suffix(".json.tmp")

        try:
            temporary_path.write_text(
                json.dumps(data, indent=2, sort_keys=True),
                encoding="utf-8",
            )
            temporary_path.replace(self.registry_path)
        except OSError as exc:
            raise HumanReviewPacketRegistryError(
                "Human review packet registry could not be written"
            ) from exc
        finally:
            if temporary_path.exists():
                temporary_path.unlink()

    def _validate_registry_path(self, registry_path: Path) -> Path:
        resolved = registry_path.resolve()

        if not self._is_within(resolved, self.intelligence_root):
            raise HumanReviewPacketRegistryError(
                "Human review packet registry must stay inside reports/intelligence"
            )

        if resolved.suffix != ".json":
            raise HumanReviewPacketRegistryError(
                "Human review packet registry must be a JSON file"
            )

        return resolved

    def _validate_packet_output_dir(self, output_dir: Path) -> Path:
        resolved = output_dir.resolve()

        if not self._is_within(resolved, self.intelligence_root):
            raise HumanReviewPacketRegistryError(
                "Human review packets must stay inside reports/intelligence"
            )

        return resolved

    def _validate_packet_output_path(self, output_path: Path) -> Path:
        if output_path.is_absolute():
            resolved = output_path.resolve()
        else:
            resolved = (self.project_root / output_path).resolve()

        if not self._is_within(resolved, self.packet_output_dir):
            raise HumanReviewPacketRegistryError(
                "Registered packet must be inside the approved packet directory"
            )

        if resolved.suffix != ".md":
            raise HumanReviewPacketRegistryError(
                "Registered human review packet must be a Markdown file"
            )

        return resolved

    def _normalize_project_path(self, path: Path) -> str:
        try:
            return self.path_normalizer.normalize(str(path))
        except PathNormalizerError as exc:
            raise HumanReviewPacketRegistryError(
                "Packet path could not be safely normalized"
            ) from exc

    @staticmethod
    def _is_within(path: Path, root: Path) -> bool:
        try:
            path.relative_to(root)
            return True
        except ValueError:
            return False
