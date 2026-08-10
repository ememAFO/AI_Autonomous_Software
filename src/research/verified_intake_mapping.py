"""Stage 4F mapping from verified intake to validation evidence.

Preparation is read-only. Application requires a separately completed mapping
approval file and an explicit apply flag. Imported public evidence remains
secondary or risk evidence and never becomes human-attested first-party
evidence.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any
from uuid import uuid4

from src.hermes.validation_evidence_log import (
    ValidationEvidenceLog,
    ValidationEvidenceLogError,
)
from src.hermes.validation_evidence_summary import (
    ValidationEvidenceSummarizer,
)
from src.research.verified_intake_mapping_storage import (
    MappingPacketRegistry,
    ValidationEvidenceImportRegistry,
)


class VerifiedIntakeMappingError(ValueError):
    """Raised when Stage 4F mapping or import fails closed."""


class MappingEligibility(StrEnum):
    ELIGIBLE = "eligible"
    BLOCKED = "blocked"


class MappingDecision(StrEnum):
    APPROVE = "APPROVE"
    HOLD = "HOLD"
    REJECT = "REJECT"


REQUIRED_INTAKE_FIELDS = frozenset(
    {
        "resolution_id",
        "packet_id",
        "packet_hash",
        "workflow_id",
        "review_id",
        "source_id",
        "reviewer_reference",
        "decision",
        "decision_reason",
        "evidence_summary",
        "classification",
        "signal_strength",
        "supports_validation",
        "canonical_url",
        "title",
        "adapter_name",
        "adapter_version",
        "retrieved_at",
        "content_hash",
        "candidate_queue_reference",
        "verified_at",
    }
)

TRUST_TYPE_RULES = {
    ValidationEvidenceLog.PUBLIC_DATASET: {
        "manual_research",
        "risk_finding",
    },
    ValidationEvidenceLog.PUBLIC_COMPETITOR: {
        "competitor_check",
        "risk_finding",
    },
}


@dataclass(frozen=True)
class ValidationEvidenceMappingItem:
    mapping_id: str
    source_id: str
    review_id: str
    title: str
    canonical_url: str
    classification: str
    source_trust: str
    evidence_type: str
    evidence_summary: str
    source_reference: str
    signal_strength: str
    supports_validation: bool
    notes: str
    mapping_rationale: str
    gate_role: str
    first_party_eligible: bool
    eligibility: MappingEligibility
    blocking_reasons: tuple[str, ...] = ()


@dataclass(frozen=True)
class VerifiedIntakeMappingPacket:
    packet_id: str
    workflow_id: str
    policy_id: str
    policy_path: str
    policy_hash: str
    resolution_id: str
    resolution_path: str
    resolution_hash: str
    intake_path: str
    intake_hash: str
    theme: str
    validation_plan_path: str
    target_log_path: str
    total_records: int
    eligible_records: int
    blocked_records: int
    proposed_primary_entries: int
    proposed_secondary_entries: int
    proposed_risk_entries: int
    items: tuple[ValidationEvidenceMappingItem, ...]
    created_at: str
    packet_hash: str


@dataclass(frozen=True)
class ValidationEvidenceImportResult:
    import_id: str
    packet_id: str
    packet_hash: str
    workflow_id: str
    approval_reference: str
    imported: int
    held: int
    rejected: int
    blocked_by_mapping_gate: int
    target_log_path: str
    import_registry_path: str
    before_summary: dict[str, Any]
    after_summary: dict[str, Any]
    imported_source_references: tuple[str, ...]
    applied_at: str
    authorized_actions: dict[str, bool] = field(
        default_factory=lambda: {
            "validation_evidence_log_append": True,
        }
    )
    protected_actions: dict[str, bool] = field(
        default_factory=lambda: {
            "approved_registry_modified": False,
            "verified_intake_modified": False,
            "theme_state_modified": False,
            "public_action_taken": False,
            "automatic_outreach": False,
        }
    )


class VerifiedIntakeMappingService:
    """Prepare and apply a controlled verified-intake mapping."""

    POLICY_VERSION = "STAGE4F-0.1"
    INTAKE_ROOT = Path("data/research/verified_evidence_intake")
    RESOLUTION_ROOT = Path(
        "reports/research/evidence_review_resolutions"
    )
    PACKET_ROOT = Path(
        "reports/research/verified_intake_mappings"
    )
    IMPORT_REPORT_ROOT = Path(
        "reports/research/validation_evidence_imports"
    )
    POLICY_ROOT = Path("config")

    def __init__(
        self,
        *,
        packet_registry: MappingPacketRegistry | None = None,
        import_registry: ValidationEvidenceImportRegistry | None = None,
    ) -> None:
        self.project_root = Path.cwd().resolve()
        self.intake_root = (
            self.project_root / self.INTAKE_ROOT
        ).resolve()
        self.resolution_root = (
            self.project_root / self.RESOLUTION_ROOT
        ).resolve()
        self.packet_root = (
            self.project_root / self.PACKET_ROOT
        ).resolve()
        self.import_report_root = (
            self.project_root / self.IMPORT_REPORT_ROOT
        ).resolve()
        self.policy_root = (
            self.project_root / self.POLICY_ROOT
        ).resolve()
        self.packet_registry = (
            packet_registry or MappingPacketRegistry()
        )
        self.import_registry = (
            import_registry or ValidationEvidenceImportRegistry()
        )

    def prepare(
        self,
        *,
        intake_file: str | Path,
        resolution_file: str | Path,
        policy_file: str | Path,
        packet_output: str | Path,
        approval_template_output: str | Path,
    ) -> VerifiedIntakeMappingPacket:
        intake_path = self._controlled_file(
            Path(intake_file),
            root=self.intake_root,
            suffix=".jsonl",
            label="verified intake",
        )
        resolution_path = self._controlled_file(
            Path(resolution_file),
            root=self.resolution_root,
            suffix=".json",
            label="Stage 4E resolution",
        )
        policy_path = self._controlled_file(
            Path(policy_file),
            root=self.policy_root,
            suffix=".json",
            label="mapping policy",
        )
        packet_path = self._controlled_output(
            Path(packet_output),
            root=self.packet_root,
            suffix=".json",
            label="mapping packet",
        )
        approval_path = self._controlled_output(
            Path(approval_template_output),
            root=self.packet_root,
            suffix=".json",
            label="mapping approval template",
        )

        resolution = self._load_object(resolution_path)
        policy = self._load_object(policy_path)
        intake_records = self._load_jsonl(intake_path)

        workflow_id = self._required_text(
            "resolution workflow_id",
            resolution.get("workflow_id", ""),
        )
        policy_workflow = self._required_text(
            "policy workflow_id",
            policy.get("workflow_id", ""),
        )
        if workflow_id != policy_workflow:
            raise VerifiedIntakeMappingError(
                "Mapping policy workflow_id does not match resolution"
            )

        resolution_id = self._required_text(
            "resolution_id",
            resolution.get("resolution_id", ""),
        )
        expected_intake_path = Path(
            str(resolution.get("verified_intake_path", ""))
        ).resolve()
        if expected_intake_path != intake_path:
            raise VerifiedIntakeMappingError(
                "Resolution verified_intake_path does not match input"
            )
        if int(resolution.get("approved", -1)) != len(intake_records):
            raise VerifiedIntakeMappingError(
                "Verified intake count does not match resolution approval count"
            )

        theme = self._required_text(
            "theme",
            policy.get("theme", ""),
        )
        validation_plan_path = self._required_text(
            "validation_plan_path",
            policy.get("validation_plan_path", ""),
        )
        plan_path = (
            self.project_root / validation_plan_path
        ).resolve()
        if not self._is_within(
            plan_path,
            (self.project_root / "reports/intelligence").resolve(),
        ):
            raise VerifiedIntakeMappingError(
                "Validation plan path is outside reports/intelligence"
            )
        if plan_path.suffix != ".md":
            raise VerifiedIntakeMappingError(
                "Validation plan must be a Markdown file"
            )
        if not plan_path.is_file():
            raise VerifiedIntakeMappingError(
                f"Validation plan does not exist: {validation_plan_path}"
            )

        target_log_path = self._required_text(
            "target_log_path",
            policy.get("target_log_path", ""),
        )
        target_log = ValidationEvidenceLog(
            log_path=target_log_path
        )
        existing_references = {
            entry.source_reference
            for entry in target_log.list_entries()
        }

        raw_mappings = policy.get("source_mappings")
        if not isinstance(raw_mappings, dict):
            raise VerifiedIntakeMappingError(
                "Policy source_mappings must be an object"
            )

        items: list[ValidationEvidenceMappingItem] = []
        seen_source_ids: set[str] = set()
        seen_review_ids: set[str] = set()
        seen_references: set[str] = set()

        for record in intake_records:
            reasons = self._intake_blocking_reasons(
                record=record,
                workflow_id=workflow_id,
                resolution_id=resolution_id,
                resolution=resolution,
            )
            source_id = str(record.get("source_id", "")).strip()
            review_id = str(record.get("review_id", "")).strip()
            mapping = raw_mappings.get(source_id)

            if source_id in seen_source_ids:
                reasons.append("duplicate_source_id")
            elif source_id:
                seen_source_ids.add(source_id)
            if review_id in seen_review_ids:
                reasons.append("duplicate_review_id")
            elif review_id:
                seen_review_ids.add(review_id)

            source_trust = ""
            evidence_type = ""
            mapping_rationale = ""
            if not isinstance(mapping, dict):
                reasons.append("source_mapping_missing")
            else:
                source_trust = str(
                    mapping.get("source_trust", "")
                ).strip().lower()
                evidence_type = str(
                    mapping.get("evidence_type", "")
                ).strip().lower()
                mapping_rationale = str(
                    mapping.get("rationale", "")
                ).strip()
                reasons.extend(
                    self._mapping_rule_reasons(
                        source_trust=source_trust,
                        evidence_type=evidence_type,
                        rationale=mapping_rationale,
                    )
                )

            source_reference = self._source_reference(
                workflow_id=workflow_id,
                source_id=source_id,
                review_id=review_id,
            )
            if source_reference in seen_references:
                reasons.append("duplicate_source_reference_in_batch")
            else:
                seen_references.add(source_reference)
            if source_reference in existing_references:
                reasons.append("source_reference_already_in_validation_log")

            gate_role = self._gate_role(evidence_type)
            notes = self._notes(
                record=record,
                mapping_rationale=mapping_rationale,
                gate_role=gate_role,
            )
            item = ValidationEvidenceMappingItem(
                mapping_id=self._mapping_id(
                    workflow_id=workflow_id,
                    source_id=source_id,
                    review_id=review_id,
                    source_trust=source_trust,
                    evidence_type=evidence_type,
                ),
                source_id=source_id,
                review_id=review_id,
                title=str(record.get("title", "")).strip(),
                canonical_url=str(
                    record.get("canonical_url", "")
                ).strip(),
                classification=str(
                    record.get("classification", "")
                ).strip().lower(),
                source_trust=source_trust,
                evidence_type=evidence_type,
                evidence_summary=str(
                    record.get("evidence_summary", "")
                ).strip(),
                source_reference=source_reference,
                signal_strength=str(
                    record.get("signal_strength", "")
                ).strip().lower(),
                supports_validation=bool(
                    record.get("supports_validation", False)
                ),
                notes=notes,
                mapping_rationale=mapping_rationale,
                gate_role=gate_role,
                first_party_eligible=False,
                eligibility=(
                    MappingEligibility.BLOCKED
                    if reasons
                    else MappingEligibility.ELIGIBLE
                ),
                blocking_reasons=tuple(dict.fromkeys(reasons)),
            )
            items.append(item)

        policy_id = self._required_text(
            "policy_id",
            policy.get("policy_id", ""),
        )
        created_at = datetime.now(UTC).isoformat()
        packet_id = (
            "VIM-"
            + self._safe_component(workflow_id)[:72]
            + "-"
            + uuid4().hex[:12]
        )
        packet_without_hash = {
            "packet_id": packet_id,
            "workflow_id": workflow_id,
            "policy_id": policy_id,
            "policy_path": self._project_path(policy_path),
            "policy_hash": self._file_hash(policy_path),
            "resolution_id": resolution_id,
            "resolution_path": self._project_path(
                resolution_path
            ),
            "resolution_hash": self._file_hash(
                resolution_path
            ),
            "intake_path": self._project_path(intake_path),
            "intake_hash": self._file_hash(intake_path),
            "theme": theme,
            "validation_plan_path": validation_plan_path,
            "target_log_path": target_log_path,
            "total_records": len(items),
            "eligible_records": sum(
                item.eligibility is MappingEligibility.ELIGIBLE
                for item in items
            ),
            "blocked_records": sum(
                item.eligibility is MappingEligibility.BLOCKED
                for item in items
            ),
            "proposed_primary_entries": 0,
            "proposed_secondary_entries": sum(
                item.eligibility is MappingEligibility.ELIGIBLE
                and item.gate_role == "secondary"
                for item in items
            ),
            "proposed_risk_entries": sum(
                item.eligibility is MappingEligibility.ELIGIBLE
                and item.gate_role == "risk"
                for item in items
            ),
            "items": [
                self._item_payload(item)
                for item in items
            ],
            "created_at": created_at,
        }
        packet_hash = self._payload_hash(packet_without_hash)
        packet = VerifiedIntakeMappingPacket(
            packet_id=packet_id,
            workflow_id=workflow_id,
            policy_id=policy_id,
            policy_path=packet_without_hash["policy_path"],
            policy_hash=packet_without_hash["policy_hash"],
            resolution_id=resolution_id,
            resolution_path=packet_without_hash["resolution_path"],
            resolution_hash=packet_without_hash["resolution_hash"],
            intake_path=packet_without_hash["intake_path"],
            intake_hash=packet_without_hash["intake_hash"],
            theme=theme,
            validation_plan_path=validation_plan_path,
            target_log_path=target_log_path,
            total_records=len(items),
            eligible_records=packet_without_hash["eligible_records"],
            blocked_records=packet_without_hash["blocked_records"],
            proposed_primary_entries=0,
            proposed_secondary_entries=packet_without_hash[
                "proposed_secondary_entries"
            ],
            proposed_risk_entries=packet_without_hash[
                "proposed_risk_entries"
            ],
            items=tuple(items),
            created_at=created_at,
            packet_hash=packet_hash,
        )

        packet_path.parent.mkdir(parents=True, exist_ok=True)
        packet_path.write_text(
            json.dumps(
                self.packet_payload(packet),
                indent=2,
                ensure_ascii=False,
            )
            + "\n",
            encoding="utf-8",
        )
        approval_path.write_text(
            json.dumps(
                self.approval_template(packet),
                indent=2,
                ensure_ascii=False,
            )
            + "\n",
            encoding="utf-8",
        )
        self.packet_registry.append(
            packet_id=packet.packet_id,
            packet_hash=packet.packet_hash,
            workflow_id=packet.workflow_id,
            packet_path=self._project_path(packet_path),
            approval_template_path=self._project_path(
                approval_path
            ),
            policy_id=packet.policy_id,
            created_at=packet.created_at,
        )
        return packet

    def apply(
        self,
        *,
        packet_file: str | Path,
        approval_file: str | Path,
        output_file: str | Path,
        apply_changes: bool,
    ) -> ValidationEvidenceImportResult:
        if not apply_changes:
            raise VerifiedIntakeMappingError(
                "Import requires explicit apply_changes=True"
            )
        packet_path = self._controlled_file(
            Path(packet_file),
            root=self.packet_root,
            suffix=".json",
            label="mapping packet",
        )
        approval_path = self._controlled_file(
            Path(approval_file),
            root=self.packet_root,
            suffix=".json",
            label="mapping approval",
        )
        output_path = self._controlled_output(
            Path(output_file),
            root=self.import_report_root,
            suffix=".json",
            label="mapping import report",
        )

        packet = self.packet_from_payload(
            self._load_object(packet_path)
        )
        self._verify_packet(
            packet=packet,
            packet_path=packet_path,
        )
        approval_reference, decisions = (
            self._parse_approval(
                packet=packet,
                payload=self._load_object(approval_path),
            )
        )
        if self.import_registry.has_packet(packet.packet_id):
            raise VerifiedIntakeMappingError(
                "Mapping packet has already been imported"
            )

        item_by_id = {
            item.mapping_id: item
            for item in packet.items
        }
        approved_items = [
            item_by_id[mapping_id]
            for mapping_id, decision in decisions.items()
            if decision == MappingDecision.APPROVE
        ]
        held = sum(
            decision == MappingDecision.HOLD
            for decision in decisions.values()
        )
        rejected = sum(
            decision == MappingDecision.REJECT
            for decision in decisions.values()
        )

        target_log = ValidationEvidenceLog(
            log_path=packet.target_log_path
        )
        before_entries = target_log.list_entries()
        existing_references = {
            entry.source_reference
            for entry in before_entries
        }
        duplicates = sorted(
            item.source_reference
            for item in approved_items
            if item.source_reference in existing_references
        )
        if duplicates:
            raise VerifiedIntakeMappingError(
                "Approved mapping already exists in validation log: "
                f"{duplicates}"
            )

        self._preflight_entries(
            packet=packet,
            items=approved_items,
        )
        target_path = Path(packet.target_log_path).resolve()
        before_exists = target_path.exists()
        before_bytes = (
            target_path.read_bytes() if before_exists else b""
        )

        imported_references: list[str] = []
        try:
            for item in approved_items:
                target_log.add_entry(
                    theme=packet.theme,
                    validation_plan_path=(
                        packet.validation_plan_path
                    ),
                    evidence_type=item.evidence_type,
                    evidence_summary=item.evidence_summary,
                    source_reference=item.source_reference,
                    signal_strength=item.signal_strength,
                    supports_validation=item.supports_validation,
                    source_trust=item.source_trust,
                    notes=item.notes,
                )
                imported_references.append(
                    item.source_reference
                )
        except (
            OSError,
            ValidationEvidenceLogError,
            ValueError,
        ) as exc:
            if before_exists:
                target_path.write_bytes(before_bytes)
            elif target_path.exists():
                target_path.unlink()
            raise VerifiedIntakeMappingError(
                "Validation evidence import failed and was rolled back"
            ) from exc

        summarizer = ValidationEvidenceSummarizer(target_log)
        before_summary = asdict(
            summarizer.summarize_entries(
                theme=packet.theme,
                entries=[
                    entry
                    for entry in before_entries
                    if entry.theme.lower()
                    == packet.theme.lower()
                ],
            )
        )
        after_summary = asdict(
            summarizer.summarize_theme(packet.theme)
        )
        applied_at = datetime.now(UTC).isoformat()
        import_id = "VEI-" + uuid4().hex
        registry_path = self.import_registry.append(
            {
                "import_id": import_id,
                "packet_id": packet.packet_id,
                "packet_hash": packet.packet_hash,
                "workflow_id": packet.workflow_id,
                "approval_reference": approval_reference,
                "theme": packet.theme,
                "target_log_path": packet.target_log_path,
                "imported": len(approved_items),
                "held": held,
                "rejected": rejected,
                "imported_source_references": imported_references,
                "applied_at": applied_at,
            }
        )
        result = ValidationEvidenceImportResult(
            import_id=import_id,
            packet_id=packet.packet_id,
            packet_hash=packet.packet_hash,
            workflow_id=packet.workflow_id,
            approval_reference=approval_reference,
            imported=len(approved_items),
            held=held,
            rejected=rejected,
            blocked_by_mapping_gate=packet.blocked_records,
            target_log_path=packet.target_log_path,
            import_registry_path=self._project_path(
                registry_path
            ),
            before_summary=before_summary,
            after_summary=after_summary,
            imported_source_references=tuple(
                imported_references
            ),
            applied_at=applied_at,
        )
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(
                asdict(result),
                indent=2,
                ensure_ascii=False,
            )
            + "\n",
            encoding="utf-8",
        )
        return result

    def _preflight_entries(
        self,
        *,
        packet: VerifiedIntakeMappingPacket,
        items: list[ValidationEvidenceMappingItem],
    ) -> None:
        preflight_dir = (
            self.project_root
            / "reports/intelligence/verified_intake_mapping_preflight"
        )
        preflight_dir.mkdir(parents=True, exist_ok=True)
        preflight_path = (
            preflight_dir
            / f"{self._safe_component(packet.packet_id)}.json"
        )
        target_path = Path(packet.target_log_path).resolve()
        if target_path.exists():
            preflight_path.write_bytes(target_path.read_bytes())
        elif preflight_path.exists():
            preflight_path.unlink()
        try:
            preflight_log = ValidationEvidenceLog(
                log_path=preflight_path
            )
            for item in items:
                preflight_log.add_entry(
                    theme=packet.theme,
                    validation_plan_path=(
                        packet.validation_plan_path
                    ),
                    evidence_type=item.evidence_type,
                    evidence_summary=item.evidence_summary,
                    source_reference=item.source_reference,
                    signal_strength=item.signal_strength,
                    supports_validation=item.supports_validation,
                    source_trust=item.source_trust,
                    notes=item.notes,
                )
        except (
            OSError,
            ValidationEvidenceLogError,
            ValueError,
        ) as exc:
            raise VerifiedIntakeMappingError(
                "Mapped entries failed validation evidence preflight"
            ) from exc
        finally:
            if preflight_path.exists():
                preflight_path.unlink()

    def _verify_packet(
        self,
        *,
        packet: VerifiedIntakeMappingPacket,
        packet_path: Path,
    ) -> None:
        intake_path = (
            self.project_root / packet.intake_path
        ).resolve()
        resolution_path = (
            self.project_root / packet.resolution_path
        ).resolve()
        policy_path = (
            self.project_root / packet.policy_path
        ).resolve()
        if self._file_hash(intake_path) != packet.intake_hash:
            raise VerifiedIntakeMappingError(
                "Verified intake changed after mapping preparation"
            )
        if self._file_hash(resolution_path) != packet.resolution_hash:
            raise VerifiedIntakeMappingError(
                "Stage 4E resolution changed after mapping preparation"
            )
        if self._file_hash(policy_path) != packet.policy_hash:
            raise VerifiedIntakeMappingError(
                "Mapping policy changed after mapping preparation"
            )
        payload = self.packet_payload(packet)
        supplied_hash = payload.pop("packet_hash")
        if self._payload_hash(payload) != supplied_hash:
            raise VerifiedIntakeMappingError(
                "Mapping packet hash verification failed"
            )
        registered = self.packet_registry.find(packet.packet_id)
        if registered is None:
            raise VerifiedIntakeMappingError(
                "Mapping packet is not registered"
            )
        if registered["packet_hash"] != packet.packet_hash:
            raise VerifiedIntakeMappingError(
                "Registered mapping packet hash does not match"
            )
        if registered["packet_path"] != self._project_path(
            packet_path
        ):
            raise VerifiedIntakeMappingError(
                "Registered mapping packet path does not match"
            )

    def _parse_approval(
        self,
        *,
        packet: VerifiedIntakeMappingPacket,
        payload: dict[str, Any],
    ) -> tuple[str, dict[str, MappingDecision]]:
        if str(payload.get("packet_id", "")) != packet.packet_id:
            raise VerifiedIntakeMappingError(
                "Approval packet_id does not match"
            )
        if str(payload.get("packet_hash", "")) != packet.packet_hash:
            raise VerifiedIntakeMappingError(
                "Approval packet_hash does not match"
            )
        approval_reference = self._audit_reference(
            payload.get("approval_reference", "")
        )
        raw_decisions = payload.get("decisions")
        if not isinstance(raw_decisions, list):
            raise VerifiedIntakeMappingError(
                "Approval decisions must be a list"
            )

        eligible_ids = {
            item.mapping_id
            for item in packet.items
            if item.eligibility is MappingEligibility.ELIGIBLE
        }
        decisions: dict[str, MappingDecision] = {}
        for raw in raw_decisions:
            if not isinstance(raw, dict):
                raise VerifiedIntakeMappingError(
                    "Every mapping decision must be an object"
                )
            mapping_id = self._required_text(
                "mapping_id",
                raw.get("mapping_id", ""),
            )
            if mapping_id in decisions:
                raise VerifiedIntakeMappingError(
                    f"Duplicate mapping decision: {mapping_id}"
                )
            if mapping_id not in eligible_ids:
                raise VerifiedIntakeMappingError(
                    "Approval references blocked or unknown mapping: "
                    f"{mapping_id}"
                )
            try:
                decision = MappingDecision(
                    self._required_text(
                        "decision",
                        raw.get("decision", ""),
                    ).upper()
                )
            except ValueError as exc:
                raise VerifiedIntakeMappingError(
                    "Mapping decision must be APPROVE, HOLD, or REJECT"
                ) from exc
            self._required_text(
                "reason",
                raw.get("reason", ""),
            )
            decisions[mapping_id] = decision

        missing = sorted(eligible_ids - decisions.keys())
        if missing:
            raise VerifiedIntakeMappingError(
                "Every eligible mapping requires a decision. "
                f"Missing: {missing}"
            )
        return approval_reference, decisions

    def _intake_blocking_reasons(
        self,
        *,
        record: dict[str, Any],
        workflow_id: str,
        resolution_id: str,
        resolution: dict[str, Any],
    ) -> list[str]:
        reasons: list[str] = []
        missing = sorted(
            field
            for field in REQUIRED_INTAKE_FIELDS
            if field not in record
        )
        if missing:
            reasons.append(
                "missing_fields:" + ",".join(missing)
            )
        if str(record.get("workflow_id", "")) != workflow_id:
            reasons.append("workflow_id_mismatch")
        if str(record.get("resolution_id", "")) != resolution_id:
            reasons.append("resolution_id_mismatch")
        if str(record.get("packet_id", "")) != str(
            resolution.get("packet_id", "")
        ):
            reasons.append("packet_id_mismatch")
        if str(record.get("packet_hash", "")) != str(
            resolution.get("packet_hash", "")
        ):
            reasons.append("packet_hash_mismatch")
        if str(record.get("decision", "")).upper() != "APPROVE":
            reasons.append("intake_decision_not_approved")
        for field_name in (
            "source_id",
            "review_id",
            "reviewer_reference",
            "evidence_summary",
            "classification",
            "signal_strength",
            "canonical_url",
            "title",
            "content_hash",
        ):
            if not str(record.get(field_name, "")).strip():
                reasons.append(f"{field_name}_missing")
        if not isinstance(record.get("supports_validation"), bool):
            reasons.append("supports_validation_not_boolean")
        return reasons

    @staticmethod
    def _mapping_rule_reasons(
        *,
        source_trust: str,
        evidence_type: str,
        rationale: str,
    ) -> list[str]:
        reasons: list[str] = []
        allowed_types = TRUST_TYPE_RULES.get(source_trust)
        if allowed_types is None:
            reasons.append("unsupported_source_trust")
        elif evidence_type not in allowed_types:
            reasons.append("source_trust_evidence_type_mismatch")
        if not rationale:
            reasons.append("mapping_rationale_missing")
        if evidence_type in ValidationEvidenceLog.PRIMARY_EVIDENCE_TYPES:
            reasons.append("public_mapping_cannot_be_primary")
        if source_trust == (
            ValidationEvidenceLog.HUMAN_ATTESTED_FIRST_PARTY
        ):
            reasons.append("public_mapping_cannot_be_first_party")
        return reasons

    @staticmethod
    def _gate_role(evidence_type: str) -> str:
        if evidence_type in {"manual_research", "competitor_check"}:
            return "secondary"
        if evidence_type == "risk_finding":
            return "risk"
        return "blocked"

    @staticmethod
    def _source_reference(
        *,
        workflow_id: str,
        source_id: str,
        review_id: str,
    ) -> str:
        return (
            f"stage4e:{workflow_id}:{source_id}:{review_id}"
        )

    @staticmethod
    def _notes(
        *,
        record: dict[str, Any],
        mapping_rationale: str,
        gate_role: str,
    ) -> str:
        fields = [
            (
                "Imported through Stage 4F from human-approved Stage 4E "
                "verified intake."
            ),
            f"canonical_url={record.get('canonical_url', '')}",
            f"classification={record.get('classification', '')}",
            (
                f"adapter={record.get('adapter_name', '')}:"
                f"{record.get('adapter_version', '')}"
            ),
            f"content_hash={record.get('content_hash', '')}",
            f"resolution_id={record.get('resolution_id', '')}",
            f"stage4e_packet_id={record.get('packet_id', '')}",
            f"gate_role={gate_role}",
            "first_party_eligible=false",
            "does_not_satisfy_primary_threshold=true",
            f"mapping_rationale={mapping_rationale}",
        ]
        return " ".join(fields)

    @staticmethod
    def _mapping_id(
        *,
        workflow_id: str,
        source_id: str,
        review_id: str,
        source_trust: str,
        evidence_type: str,
    ) -> str:
        material = (
            f"{workflow_id}|{source_id}|{review_id}|"
            f"{source_trust}|{evidence_type}"
        ).encode()
        return "VIMI-" + hashlib.sha256(material).hexdigest()[:20]

    @staticmethod
    def _item_payload(
        item: ValidationEvidenceMappingItem,
    ) -> dict[str, Any]:
        payload = asdict(item)
        payload["eligibility"] = item.eligibility.value
        payload["blocking_reasons"] = list(
            item.blocking_reasons
        )
        return payload

    @staticmethod
    def packet_payload(
        packet: VerifiedIntakeMappingPacket,
    ) -> dict[str, Any]:
        payload = asdict(packet)
        payload["items"] = [
            {
                **asdict(item),
                "eligibility": item.eligibility.value,
                "blocking_reasons": list(
                    item.blocking_reasons
                ),
            }
            for item in packet.items
        ]
        return payload

    @classmethod
    def packet_from_payload(
        cls,
        payload: dict[str, Any],
    ) -> VerifiedIntakeMappingPacket:
        raw_items = payload.get("items")
        if not isinstance(raw_items, list):
            raise VerifiedIntakeMappingError(
                "Mapping packet items must be a list"
            )
        items: list[ValidationEvidenceMappingItem] = []
        for raw in raw_items:
            if not isinstance(raw, dict):
                raise VerifiedIntakeMappingError(
                    "Mapping packet item must be an object"
                )
            try:
                eligibility = MappingEligibility(
                    str(raw["eligibility"])
                )
            except (KeyError, ValueError) as exc:
                raise VerifiedIntakeMappingError(
                    "Mapping packet item has invalid eligibility"
                ) from exc
            items.append(
                ValidationEvidenceMappingItem(
                    mapping_id=str(raw.get("mapping_id", "")),
                    source_id=str(raw.get("source_id", "")),
                    review_id=str(raw.get("review_id", "")),
                    title=str(raw.get("title", "")),
                    canonical_url=str(
                        raw.get("canonical_url", "")
                    ),
                    classification=str(
                        raw.get("classification", "")
                    ),
                    source_trust=str(
                        raw.get("source_trust", "")
                    ),
                    evidence_type=str(
                        raw.get("evidence_type", "")
                    ),
                    evidence_summary=str(
                        raw.get("evidence_summary", "")
                    ),
                    source_reference=str(
                        raw.get("source_reference", "")
                    ),
                    signal_strength=str(
                        raw.get("signal_strength", "")
                    ),
                    supports_validation=bool(
                        raw.get("supports_validation", False)
                    ),
                    notes=str(raw.get("notes", "")),
                    mapping_rationale=str(
                        raw.get("mapping_rationale", "")
                    ),
                    gate_role=str(
                        raw.get("gate_role", "")
                    ),
                    first_party_eligible=bool(
                        raw.get("first_party_eligible", False)
                    ),
                    eligibility=eligibility,
                    blocking_reasons=tuple(
                        str(reason)
                        for reason in raw.get(
                            "blocking_reasons",
                            [],
                        )
                    ),
                )
            )
        try:
            return VerifiedIntakeMappingPacket(
                packet_id=str(payload["packet_id"]),
                workflow_id=str(payload["workflow_id"]),
                policy_id=str(payload["policy_id"]),
                policy_path=str(payload["policy_path"]),
                policy_hash=str(payload["policy_hash"]),
                resolution_id=str(payload["resolution_id"]),
                resolution_path=str(payload["resolution_path"]),
                resolution_hash=str(payload["resolution_hash"]),
                intake_path=str(payload["intake_path"]),
                intake_hash=str(payload["intake_hash"]),
                theme=str(payload["theme"]),
                validation_plan_path=str(
                    payload["validation_plan_path"]
                ),
                target_log_path=str(
                    payload["target_log_path"]
                ),
                total_records=int(payload["total_records"]),
                eligible_records=int(
                    payload["eligible_records"]
                ),
                blocked_records=int(
                    payload["blocked_records"]
                ),
                proposed_primary_entries=int(
                    payload["proposed_primary_entries"]
                ),
                proposed_secondary_entries=int(
                    payload["proposed_secondary_entries"]
                ),
                proposed_risk_entries=int(
                    payload["proposed_risk_entries"]
                ),
                items=tuple(items),
                created_at=str(payload["created_at"]),
                packet_hash=str(payload["packet_hash"]),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise VerifiedIntakeMappingError(
                "Mapping packet is missing required metadata"
            ) from exc

    @staticmethod
    def approval_template(
        packet: VerifiedIntakeMappingPacket,
    ) -> dict[str, Any]:
        return {
            "packet_id": packet.packet_id,
            "packet_hash": packet.packet_hash,
            "approval_reference": "",
            "instructions": (
                "Review every eligible source-trust and evidence-type "
                "mapping. APPROVE permits an append to the validation "
                "evidence log only when the apply command is run with "
                "--apply. These public records remain secondary or risk "
                "evidence and contribute zero primary evidence."
            ),
            "decisions": [
                {
                    "mapping_id": item.mapping_id,
                    "source_id": item.source_id,
                    "title": item.title,
                    "source_trust": item.source_trust,
                    "evidence_type": item.evidence_type,
                    "gate_role": item.gate_role,
                    "first_party_eligible": False,
                    "decision": "",
                    "reason": "",
                }
                for item in packet.items
                if item.eligibility is MappingEligibility.ELIGIBLE
            ],
            "blocked_mappings": [
                {
                    "mapping_id": item.mapping_id,
                    "source_id": item.source_id,
                    "blocking_reasons": list(
                        item.blocking_reasons
                    ),
                }
                for item in packet.items
                if item.eligibility is MappingEligibility.BLOCKED
            ],
        }

    def _controlled_file(
        self,
        path: Path,
        *,
        root: Path,
        suffix: str,
        label: str,
    ) -> Path:
        resolved = path.resolve()
        if not self._is_within(resolved, root):
            raise VerifiedIntakeMappingError(
                f"{label} must stay inside {self._project_path(root)}"
            )
        if resolved.suffix != suffix:
            raise VerifiedIntakeMappingError(
                f"{label} must use {suffix}"
            )
        if not resolved.is_file():
            raise VerifiedIntakeMappingError(
                f"{label} does not exist: {path}"
            )
        return resolved

    def _controlled_output(
        self,
        path: Path,
        *,
        root: Path,
        suffix: str,
        label: str,
    ) -> Path:
        resolved = path.resolve()
        if not self._is_within(resolved, root):
            raise VerifiedIntakeMappingError(
                f"{label} must stay inside {self._project_path(root)}"
            )
        if resolved.suffix != suffix:
            raise VerifiedIntakeMappingError(
                f"{label} must use {suffix}"
            )
        return resolved

    @staticmethod
    def _load_object(path: Path) -> dict[str, Any]:
        try:
            payload = json.loads(
                path.read_text(encoding="utf-8")
            )
        except (OSError, json.JSONDecodeError) as exc:
            raise VerifiedIntakeMappingError(
                f"Could not read JSON object: {path}"
            ) from exc
        if not isinstance(payload, dict):
            raise VerifiedIntakeMappingError(
                "JSON file must contain an object"
            )
        return payload

    @staticmethod
    def _load_jsonl(path: Path) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []
        try:
            lines = path.read_text(
                encoding="utf-8"
            ).splitlines()
        except OSError as exc:
            raise VerifiedIntakeMappingError(
                "Verified intake could not be read"
            ) from exc
        for line_number, line in enumerate(lines, start=1):
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                raise VerifiedIntakeMappingError(
                    "Verified intake contains invalid JSON at "
                    f"line {line_number}"
                ) from exc
            if not isinstance(record, dict):
                raise VerifiedIntakeMappingError(
                    "Every verified intake line must be an object"
                )
            records.append(record)
        if not records:
            raise VerifiedIntakeMappingError(
                "Verified intake contains no records"
            )
        return records

    def _project_path(self, path: Path) -> str:
        try:
            return str(path.resolve().relative_to(self.project_root))
        except ValueError as exc:
            raise VerifiedIntakeMappingError(
                "Path is outside the project root"
            ) from exc

    @staticmethod
    def _file_hash(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(
                lambda: handle.read(65_536),
                b"",
            ):
                digest.update(chunk)
        return digest.hexdigest()

    @staticmethod
    def _payload_hash(payload: dict[str, Any]) -> str:
        encoded = json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode()
        return hashlib.sha256(encoded).hexdigest()

    @staticmethod
    def _required_text(
        field_name: str,
        value: Any,
    ) -> str:
        if not isinstance(value, str) or not value.strip():
            raise VerifiedIntakeMappingError(
                f"{field_name} is required"
            )
        return " ".join(value.split())

    @classmethod
    def _audit_reference(cls, value: Any) -> str:
        reference = cls._required_text(
            "approval_reference",
            value,
        )
        if len(reference) > 120:
            raise VerifiedIntakeMappingError(
                "approval_reference is too long"
            )
        if not all(
            character.isalnum()
            or character in {"_", "-", "."}
            for character in reference
        ):
            raise VerifiedIntakeMappingError(
                "approval_reference may contain only letters, numbers, "
                "dots, hyphens, and underscores"
            )
        return reference

    @staticmethod
    def _safe_component(value: str) -> str:
        safe = "".join(
            character
            for character in value
            if character.isalnum() or character in {"-", "_"}
        ).strip("._")
        if not safe:
            raise VerifiedIntakeMappingError(
                "Invalid identifier"
            )
        return safe[:120]

    @staticmethod
    def _is_within(path: Path, root: Path) -> bool:
        try:
            path.relative_to(root)
            return True
        except ValueError:
            return False
