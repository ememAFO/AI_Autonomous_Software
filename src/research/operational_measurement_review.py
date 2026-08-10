"""Prepare and resolve Stage 4G v0.2 measurement reviews."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any
from uuid import uuid4

from src.research.operational_measurement_storage import (
    ControlledMeasurementStore,
    OperationalMeasurementCandidateStore,
    OperationalMeasurementDecisionStore,
    OperationalMeasurementPacketRegistry,
    OperationalMeasurementVerifiedStore,
)


class OperationalMeasurementReviewError(ValueError):
    """Raised when measurement review fails closed."""


class MeasurementEligibility(StrEnum):
    ELIGIBLE = "eligible"
    BLOCKED = "blocked"


class MeasurementDecision(StrEnum):
    APPROVE = "APPROVE"
    HOLD = "HOLD"
    REJECT = "REJECT"


TOKEN_PATTERN = re.compile(r"^[A-Za-z0-9_.:-]{3,120}$")


@dataclass(frozen=True)
class MeasurementReviewItem:
    review_id: str
    measurement_id: str
    pilot_id: str
    metric_name: str
    metric_unit: str
    comparison_method: str
    baseline_start: str
    baseline_end: str
    intervention_start: str
    observation_end: str
    baseline_sample_size: int
    observation_sample_size: int
    operational_context_codes: tuple[str, ...]
    operational_context_summary: str
    known_confounders: tuple[str, ...]
    outcome_before: float
    outcome_after: float
    absolute_change: float
    relative_change_percent: float | None
    effect_magnitude: float
    effect_direction: str
    persistence_period_days: int
    estimated_financial_effect_gbp: float | None
    manual_time_before_minutes: float | None
    manual_time_after_minutes: float | None
    manual_time_change_minutes: float | None
    feedback_reason_codes: tuple[str, ...]
    unintended_effect_codes: tuple[str, ...]
    expert_interpretation: str
    decision_taken: str
    source_reference: str
    attestor_reference: str
    candidate_hash: str
    measurement_fingerprint: str
    eligibility: MeasurementEligibility
    blocking_reasons: tuple[str, ...] = ()


@dataclass(frozen=True)
class MeasurementReviewPacket:
    packet_id: str
    campaign_id: str
    measurement_program_id: str
    policy_id: str
    policy_path: str
    policy_hash: str
    candidate_path: str
    candidate_hash: str
    theme: str
    total_measurements: int
    eligible_measurements: int
    blocked_measurements: int
    taxonomy_status: str
    validation_log_import_allowed: bool
    claim_boundary: str
    items: tuple[MeasurementReviewItem, ...]
    created_at: str
    packet_hash: str


@dataclass(frozen=True)
class MeasurementReviewResolution:
    resolution_id: str
    packet_id: str
    packet_hash: str
    campaign_id: str
    measurement_program_id: str
    reviewer_reference: str
    approved: int
    held: int
    rejected: int
    blocked_by_gate: int
    verified_measurement_path: str
    verified_measurement_hash: str
    decision_registry_path: str
    resolved_at: str
    validation_log_import_allowed: bool = False
    protected_actions: dict[str, bool] = field(
        default_factory=lambda: {
            "validation_evidence_log_modified": False,
            "theme_state_modified": False,
            "build_approved": False,
            "public_action_taken": False,
            "automatic_outreach": False,
        }
    )


class OperationalMeasurementReviewService:
    """Prepare packets and resolve human measurement decisions."""

    SCHEMA_VERSION = "STAGE4G-0.2"
    POLICY_ROOT = Path("config")
    PACKET_ROOT = Path(
        "reports/research/operational_measurement_review_packets"
    )
    RESOLUTION_ROOT = Path(
        "reports/research/operational_measurement_review_resolutions"
    )

    def __init__(
        self,
        *,
        candidate_store: (
            OperationalMeasurementCandidateStore | None
        ) = None,
        packet_registry: (
            OperationalMeasurementPacketRegistry | None
        ) = None,
        decision_store: (
            OperationalMeasurementDecisionStore | None
        ) = None,
        verified_store: (
            OperationalMeasurementVerifiedStore | None
        ) = None,
    ) -> None:
        self.project_root = Path.cwd().resolve()
        self.policy_root = (
            self.project_root / self.POLICY_ROOT
        ).resolve()
        self.packet_root = (
            self.project_root / self.PACKET_ROOT
        ).resolve()
        self.resolution_root = (
            self.project_root / self.RESOLUTION_ROOT
        ).resolve()
        self.candidate_store = (
            candidate_store
            or OperationalMeasurementCandidateStore()
        )
        self.packet_registry = (
            packet_registry
            or OperationalMeasurementPacketRegistry()
        )
        self.decision_store = (
            decision_store
            or OperationalMeasurementDecisionStore()
        )
        self.verified_store = (
            verified_store
            or OperationalMeasurementVerifiedStore()
        )

    def prepare(
        self,
        *,
        candidate_file: str | Path,
        policy_file: str | Path,
        packet_output: str | Path,
        decision_template_output: str | Path,
    ) -> MeasurementReviewPacket:
        policy_path = self._controlled_file(
            Path(policy_file),
            root=self.policy_root,
            suffix=".json",
            label="measurement policy",
        )
        candidate_path = self._controlled_file(
            Path(candidate_file),
            root=self.candidate_store.root,
            suffix=".jsonl",
            label="measurement candidate file",
        )
        packet_path = self._controlled_output(
            Path(packet_output),
            root=self.packet_root,
            suffix=".json",
            label="measurement review packet",
        )
        template_path = self._controlled_output(
            Path(decision_template_output),
            root=self.packet_root,
            suffix=".json",
            label="measurement decision template",
        )
        for path in (packet_path, template_path):
            if path.exists():
                raise OperationalMeasurementReviewError(
                    f"Output already exists: {path}"
                )

        policy = self._load_object(policy_path)
        campaign_id = self._required_text(
            "campaign_id",
            policy.get("campaign_id", ""),
        )
        program_id = self._required_text(
            "measurement_program_id",
            policy.get("measurement_program_id", ""),
        )
        if candidate_path != self.candidate_store.path_for(
            program_id
        ):
            raise OperationalMeasurementReviewError(
                "Candidate file does not match measurement program"
            )
        candidates = self.candidate_store.read(candidate_path)
        if not candidates:
            raise OperationalMeasurementReviewError(
                "Candidate file contains no measurements"
            )

        policy_hash = self._file_hash(policy_path)
        items: list[MeasurementReviewItem] = []
        for candidate in candidates:
            reasons = self._integrity_reasons(
                candidate,
                campaign_id=campaign_id,
                program_id=program_id,
                policy_hash=policy_hash,
            )
            eligibility = (
                MeasurementEligibility.BLOCKED
                if reasons
                else MeasurementEligibility.ELIGIBLE
            )
            items.append(
                self._review_item(
                    candidate,
                    eligibility=eligibility,
                    blocking_reasons=tuple(
                        dict.fromkeys(reasons)
                    ),
                )
            )

        candidate_hash = self._file_hash(candidate_path)
        packet_without_hash = {
            "packet_id": self._packet_id(
                program_id,
                candidate_hash,
                policy_hash,
            ),
            "campaign_id": campaign_id,
            "measurement_program_id": program_id,
            "policy_id": self._required_text(
                "policy_id",
                policy.get("policy_id", ""),
            ),
            "policy_path": self._project_path(policy_path),
            "policy_hash": policy_hash,
            "candidate_path": self._project_path(candidate_path),
            "candidate_hash": candidate_hash,
            "theme": self._required_text(
                "theme",
                policy.get("theme", ""),
            ),
            "total_measurements": len(items),
            "eligible_measurements": sum(
                item.eligibility
                is MeasurementEligibility.ELIGIBLE
                for item in items
            ),
            "blocked_measurements": sum(
                item.eligibility
                is MeasurementEligibility.BLOCKED
                for item in items
            ),
            "taxonomy_status": (
                "separate_operational_measurement"
            ),
            "validation_log_import_allowed": False,
            "claim_boundary": "observational_not_causal",
            "items": [
                self._item_payload(item) for item in items
            ],
            "created_at": datetime.now(UTC).isoformat(),
        }
        packet_hash = self._payload_hash(packet_without_hash)
        metadata = dict(packet_without_hash)
        metadata.pop("items")
        packet = MeasurementReviewPacket(
            **metadata,
            items=tuple(items),
            packet_hash=packet_hash,
        )

        registry_snapshot = ControlledMeasurementStore.snapshot(
            self.packet_registry.registry_path
        )
        try:
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
            template_path.write_text(
                json.dumps(
                    self.decision_template(packet),
                    indent=2,
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )
            self.packet_registry.append_many(
                self.packet_registry.registry_path,
                [
                    {
                        "packet_id": packet.packet_id,
                        "packet_hash": packet.packet_hash,
                        "campaign_id": packet.campaign_id,
                        "measurement_program_id": (
                            packet.measurement_program_id
                        ),
                        "packet_path": self._project_path(
                            packet_path
                        ),
                        "template_path": self._project_path(
                            template_path
                        ),
                        "created_at": packet.created_at,
                    }
                ],
            )
            return packet
        except Exception:
            ControlledMeasurementStore.restore(
                self.packet_registry.registry_path,
                registry_snapshot,
            )
            for path in (packet_path, template_path):
                if path.exists():
                    path.unlink()
            raise

    def resolve(
        self,
        *,
        packet_file: str | Path,
        decision_file: str | Path,
        output_file: str | Path,
    ) -> MeasurementReviewResolution:
        packet_path = self._controlled_file(
            Path(packet_file),
            root=self.packet_root,
            suffix=".json",
            label="measurement review packet",
        )
        decision_path = self._controlled_file(
            Path(decision_file),
            root=self.packet_root,
            suffix=".json",
            label="measurement review decision",
        )
        output_path = self._controlled_output(
            Path(output_file),
            root=self.resolution_root,
            suffix=".json",
            label="measurement review resolution",
        )
        if output_path.exists():
            raise OperationalMeasurementReviewError(
                "Measurement review resolution already exists"
            )

        packet = self.packet_from_payload(
            self._load_object(packet_path)
        )
        self._verify_packet(packet, packet_path)
        if self.decision_store.has_packet(packet.packet_id):
            raise OperationalMeasurementReviewError(
                "Measurement packet has already been resolved"
            )
        reviewer_reference, decisions = self._parse_decisions(
            packet,
            self._load_object(decision_path),
        )

        resolution_id = "OMRR-" + uuid4().hex
        item_by_id = {
            item.review_id: item for item in packet.items
        }
        approved_items = [
            item_by_id[review_id]
            for review_id, value in decisions.items()
            if value["decision"] is MeasurementDecision.APPROVE
        ]
        held = sum(
            value["decision"] is MeasurementDecision.HOLD
            for value in decisions.values()
        )
        rejected = sum(
            value["decision"] is MeasurementDecision.REJECT
            for value in decisions.values()
        )

        verified_path = self.verified_store.path_for(
            resolution_id
        )
        decision_path_out = self.decision_store.path_for(
            packet.measurement_program_id
        )
        verified_records = [
            self._verified_record(
                packet,
                item,
                resolution_id=resolution_id,
                reviewer_reference=reviewer_reference,
                reason=str(decisions[item.review_id]["reason"]),
            )
            for item in approved_items
        ]
        decision_records = [
            {
                "resolution_id": resolution_id,
                "packet_id": packet.packet_id,
                "packet_hash": packet.packet_hash,
                "campaign_id": packet.campaign_id,
                "measurement_program_id": (
                    packet.measurement_program_id
                ),
                "review_id": review_id,
                "reviewer_reference": reviewer_reference,
                "decision": value["decision"].value,
                "reason": value["reason"],
                "resolved_at": datetime.now(UTC).isoformat(),
            }
            for review_id, value in decisions.items()
        ]

        verified_snapshot = ControlledMeasurementStore.snapshot(
            verified_path
        )
        decision_snapshot = ControlledMeasurementStore.snapshot(
            decision_path_out
        )
        try:
            if verified_records:
                self.verified_store.append_many(
                    verified_path,
                    verified_records,
                )
            else:
                verified_path.parent.mkdir(
                    parents=True,
                    exist_ok=True,
                )
                verified_path.write_text("", encoding="utf-8")
            self.decision_store.append_many(
                decision_path_out,
                decision_records,
            )
            resolution = MeasurementReviewResolution(
                resolution_id=resolution_id,
                packet_id=packet.packet_id,
                packet_hash=packet.packet_hash,
                campaign_id=packet.campaign_id,
                measurement_program_id=(
                    packet.measurement_program_id
                ),
                reviewer_reference=reviewer_reference,
                approved=len(approved_items),
                held=held,
                rejected=rejected,
                blocked_by_gate=packet.blocked_measurements,
                verified_measurement_path=self._project_path(
                    verified_path
                ),
                verified_measurement_hash=self._file_hash(
                    verified_path
                ),
                decision_registry_path=self._project_path(
                    decision_path_out
                ),
                resolved_at=datetime.now(UTC).isoformat(),
            )
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(
                json.dumps(
                    asdict(resolution),
                    indent=2,
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )
            return resolution
        except Exception:
            ControlledMeasurementStore.restore(
                verified_path,
                verified_snapshot,
            )
            ControlledMeasurementStore.restore(
                decision_path_out,
                decision_snapshot,
            )
            if output_path.exists():
                output_path.unlink()
            raise

    def _integrity_reasons(
        self,
        candidate: dict[str, Any],
        *,
        campaign_id: str,
        program_id: str,
        policy_hash: str,
    ) -> list[str]:
        reasons: list[str] = []
        if str(candidate.get("campaign_id", "")) != campaign_id:
            reasons.append("campaign_id_mismatch")
        if str(
            candidate.get("measurement_program_id", "")
        ) != program_id:
            reasons.append("measurement_program_id_mismatch")
        if str(candidate.get("policy_hash", "")) != policy_hash:
            reasons.append("policy_hash_mismatch")
        if str(candidate.get("schema_version", "")) != (
            self.SCHEMA_VERSION
        ):
            reasons.append("schema_version_mismatch")
        if candidate.get("validation_log_import_allowed") is not False:
            reasons.append("validation_log_import_boundary_changed")
        if str(candidate.get("taxonomy_status", "")) != (
            "separate_operational_measurement"
        ):
            reasons.append("taxonomy_status_changed")
        supplied_hash = str(candidate.get("candidate_hash", ""))
        payload = dict(candidate)
        payload.pop("candidate_hash", None)
        if self._payload_hash(payload) != supplied_hash:
            reasons.append("candidate_hash_mismatch")
        return reasons

    def _review_item(
        self,
        candidate: dict[str, Any],
        *,
        eligibility: MeasurementEligibility,
        blocking_reasons: tuple[str, ...],
    ) -> MeasurementReviewItem:
        return MeasurementReviewItem(
            review_id=self._review_id(
                str(candidate.get("measurement_program_id", "")),
                str(candidate.get("measurement_id", "")),
                str(candidate.get("candidate_hash", "")),
            ),
            measurement_id=str(
                candidate.get("measurement_id", "")
            ),
            pilot_id=str(candidate.get("pilot_id", "")),
            metric_name=str(candidate.get("metric_name", "")),
            metric_unit=str(candidate.get("metric_unit", "")),
            comparison_method=str(
                candidate.get("comparison_method", "")
            ),
            baseline_start=str(
                candidate.get("baseline_start", "")
            ),
            baseline_end=str(candidate.get("baseline_end", "")),
            intervention_start=str(
                candidate.get("intervention_start", "")
            ),
            observation_end=str(
                candidate.get("observation_end", "")
            ),
            baseline_sample_size=int(
                candidate.get("baseline_sample_size", 0)
            ),
            observation_sample_size=int(
                candidate.get("observation_sample_size", 0)
            ),
            operational_context_codes=tuple(
                str(value)
                for value in candidate.get(
                    "operational_context_codes",
                    [],
                )
            ),
            operational_context_summary=str(
                candidate.get("operational_context_summary", "")
            ),
            known_confounders=tuple(
                str(value)
                for value in candidate.get(
                    "known_confounders",
                    [],
                )
            ),
            outcome_before=float(
                candidate.get("outcome_before", 0)
            ),
            outcome_after=float(
                candidate.get("outcome_after", 0)
            ),
            absolute_change=float(
                candidate.get("absolute_change", 0)
            ),
            relative_change_percent=(
                float(candidate["relative_change_percent"])
                if candidate.get("relative_change_percent")
                is not None
                else None
            ),
            effect_magnitude=float(
                candidate.get("effect_magnitude", 0)
            ),
            effect_direction=str(
                candidate.get("effect_direction", "")
            ),
            persistence_period_days=int(
                candidate.get("persistence_period_days", 0)
            ),
            estimated_financial_effect_gbp=(
                float(
                    candidate[
                        "estimated_financial_effect_gbp"
                    ]
                )
                if candidate.get(
                    "estimated_financial_effect_gbp"
                )
                is not None
                else None
            ),
            manual_time_before_minutes=(
                float(candidate["manual_time_before_minutes"])
                if candidate.get("manual_time_before_minutes")
                is not None
                else None
            ),
            manual_time_after_minutes=(
                float(candidate["manual_time_after_minutes"])
                if candidate.get("manual_time_after_minutes")
                is not None
                else None
            ),
            manual_time_change_minutes=(
                float(candidate["manual_time_change_minutes"])
                if candidate.get("manual_time_change_minutes")
                is not None
                else None
            ),
            feedback_reason_codes=tuple(
                str(value)
                for value in candidate.get(
                    "feedback_reason_codes",
                    [],
                )
            ),
            unintended_effect_codes=tuple(
                str(value)
                for value in candidate.get(
                    "unintended_effect_codes",
                    [],
                )
            ),
            expert_interpretation=str(
                candidate.get("expert_interpretation", "")
            ),
            decision_taken=str(
                candidate.get("decision_taken", "")
            ),
            source_reference=str(
                candidate.get("source_reference", "")
            ),
            attestor_reference=str(
                candidate.get("attestor_reference", "")
            ),
            candidate_hash=str(
                candidate.get("candidate_hash", "")
            ),
            measurement_fingerprint=str(
                candidate.get("measurement_fingerprint", "")
            ),
            eligibility=eligibility,
            blocking_reasons=blocking_reasons,
        )

    def _parse_decisions(
        self,
        packet: MeasurementReviewPacket,
        payload: dict[str, Any],
    ) -> tuple[str, dict[str, dict[str, Any]]]:
        if str(payload.get("packet_id", "")) != packet.packet_id:
            raise OperationalMeasurementReviewError(
                "Decision packet_id does not match"
            )
        if str(payload.get("packet_hash", "")) != packet.packet_hash:
            raise OperationalMeasurementReviewError(
                "Decision packet_hash does not match"
            )
        reviewer_reference = self._audit_reference(
            payload.get("reviewer_reference", ""),
            field_name="reviewer_reference",
        )
        raw_decisions = payload.get("decisions")
        if not isinstance(raw_decisions, list):
            raise OperationalMeasurementReviewError(
                "Measurement decisions must be a list"
            )

        reviewable = {
            item.review_id: item
            for item in packet.items
            if item.eligibility
            is MeasurementEligibility.ELIGIBLE
        }
        decisions: dict[str, dict[str, Any]] = {}
        for raw in raw_decisions:
            if not isinstance(raw, dict):
                raise OperationalMeasurementReviewError(
                    "Every measurement decision must be an object"
                )
            review_id = self._required_text(
                "review_id",
                raw.get("review_id", ""),
            )
            if review_id in decisions:
                raise OperationalMeasurementReviewError(
                    f"Duplicate review decision: {review_id}"
                )
            if review_id not in reviewable:
                raise OperationalMeasurementReviewError(
                    "Decision references blocked or unknown item"
                )
            try:
                decision = MeasurementDecision(
                    self._required_text(
                        "decision",
                        raw.get("decision", ""),
                    ).upper()
                )
            except ValueError as exc:
                raise OperationalMeasurementReviewError(
                    "Decision must be APPROVE, HOLD, or REJECT"
                ) from exc
            reason = self._required_text(
                "reason",
                raw.get("reason", ""),
            )
            decisions[review_id] = {
                "decision": decision,
                "reason": reason,
            }

        missing = sorted(set(reviewable) - set(decisions))
        if missing:
            raise OperationalMeasurementReviewError(
                "Every eligible measurement requires a decision. "
                f"Missing: {missing}"
            )
        return reviewer_reference, decisions

    @staticmethod
    def _verified_record(
        packet: MeasurementReviewPacket,
        item: MeasurementReviewItem,
        *,
        resolution_id: str,
        reviewer_reference: str,
        reason: str,
    ) -> dict[str, Any]:
        payload = {
            key: value
            for key, value in asdict(item).items()
            if key not in {"eligibility", "blocking_reasons"}
        }
        payload.update(
            {
                "schema_version": "STAGE4G-0.2",
                "resolution_id": resolution_id,
                "packet_id": packet.packet_id,
                "packet_hash": packet.packet_hash,
                "campaign_id": packet.campaign_id,
                "measurement_program_id": (
                    packet.measurement_program_id
                ),
                "reviewer_reference": reviewer_reference,
                "review_decision": "APPROVE",
                "review_reason": reason,
                "theme": packet.theme,
                "taxonomy_status": (
                    "separate_operational_measurement"
                ),
                "validation_log_import_allowed": False,
                "claim_boundary": "observational_not_causal",
                "verified_at": datetime.now(UTC).isoformat(),
            }
        )
        for key in (
            "operational_context_codes",
            "known_confounders",
            "feedback_reason_codes",
            "unintended_effect_codes",
        ):
            payload[key] = list(payload[key])
        return payload

    def _verify_packet(
        self,
        packet: MeasurementReviewPacket,
        packet_path: Path,
    ) -> None:
        candidate_path = (
            self.project_root / packet.candidate_path
        ).resolve()
        policy_path = (
            self.project_root / packet.policy_path
        ).resolve()
        if self._file_hash(candidate_path) != packet.candidate_hash:
            raise OperationalMeasurementReviewError(
                "Measurement candidates changed after packet creation"
            )
        if self._file_hash(policy_path) != packet.policy_hash:
            raise OperationalMeasurementReviewError(
                "Measurement policy changed after packet creation"
            )
        payload = self.packet_payload(packet)
        supplied_hash = payload.pop("packet_hash")
        if self._payload_hash(payload) != supplied_hash:
            raise OperationalMeasurementReviewError(
                "Measurement packet hash verification failed"
            )
        registered = self.packet_registry.find(packet.packet_id)
        if registered is None:
            raise OperationalMeasurementReviewError(
                "Measurement packet is not registered"
            )
        if registered["packet_hash"] != packet.packet_hash:
            raise OperationalMeasurementReviewError(
                "Registered packet hash does not match"
            )
        if registered["packet_path"] != self._project_path(
            packet_path
        ):
            raise OperationalMeasurementReviewError(
                "Registered packet path does not match"
            )

    @staticmethod
    def packet_payload(
        packet: MeasurementReviewPacket,
    ) -> dict[str, Any]:
        payload = asdict(packet)
        payload["items"] = [
            OperationalMeasurementReviewService._item_payload(
                item
            )
            for item in packet.items
        ]
        return payload

    @classmethod
    def packet_from_payload(
        cls,
        payload: dict[str, Any],
    ) -> MeasurementReviewPacket:
        raw_items = payload.get("items")
        if not isinstance(raw_items, list):
            raise OperationalMeasurementReviewError(
                "Measurement packet items must be a list"
            )
        items: list[MeasurementReviewItem] = []
        for raw in raw_items:
            if not isinstance(raw, dict):
                raise OperationalMeasurementReviewError(
                    "Measurement packet item must be an object"
                )
            try:
                eligibility = MeasurementEligibility(
                    str(raw["eligibility"])
                )
            except (KeyError, ValueError) as exc:
                raise OperationalMeasurementReviewError(
                    "Measurement item has invalid eligibility"
                ) from exc
            items.append(
                MeasurementReviewItem(
                    review_id=str(raw.get("review_id", "")),
                    measurement_id=str(
                        raw.get("measurement_id", "")
                    ),
                    pilot_id=str(raw.get("pilot_id", "")),
                    metric_name=str(raw.get("metric_name", "")),
                    metric_unit=str(raw.get("metric_unit", "")),
                    comparison_method=str(
                        raw.get("comparison_method", "")
                    ),
                    baseline_start=str(
                        raw.get("baseline_start", "")
                    ),
                    baseline_end=str(
                        raw.get("baseline_end", "")
                    ),
                    intervention_start=str(
                        raw.get("intervention_start", "")
                    ),
                    observation_end=str(
                        raw.get("observation_end", "")
                    ),
                    baseline_sample_size=int(
                        raw.get("baseline_sample_size", 0)
                    ),
                    observation_sample_size=int(
                        raw.get("observation_sample_size", 0)
                    ),
                    operational_context_codes=tuple(
                        str(value)
                        for value in raw.get(
                            "operational_context_codes",
                            [],
                        )
                    ),
                    operational_context_summary=str(
                        raw.get(
                            "operational_context_summary",
                            "",
                        )
                    ),
                    known_confounders=tuple(
                        str(value)
                        for value in raw.get(
                            "known_confounders",
                            [],
                        )
                    ),
                    outcome_before=float(
                        raw.get("outcome_before", 0)
                    ),
                    outcome_after=float(
                        raw.get("outcome_after", 0)
                    ),
                    absolute_change=float(
                        raw.get("absolute_change", 0)
                    ),
                    relative_change_percent=(
                        float(raw["relative_change_percent"])
                        if raw.get("relative_change_percent")
                        is not None
                        else None
                    ),
                    effect_magnitude=float(
                        raw.get("effect_magnitude", 0)
                    ),
                    effect_direction=str(
                        raw.get("effect_direction", "")
                    ),
                    persistence_period_days=int(
                        raw.get("persistence_period_days", 0)
                    ),
                    estimated_financial_effect_gbp=(
                        float(
                            raw[
                                "estimated_financial_effect_gbp"
                            ]
                        )
                        if raw.get(
                            "estimated_financial_effect_gbp"
                        )
                        is not None
                        else None
                    ),
                    manual_time_before_minutes=(
                        float(raw["manual_time_before_minutes"])
                        if raw.get("manual_time_before_minutes")
                        is not None
                        else None
                    ),
                    manual_time_after_minutes=(
                        float(raw["manual_time_after_minutes"])
                        if raw.get("manual_time_after_minutes")
                        is not None
                        else None
                    ),
                    manual_time_change_minutes=(
                        float(raw["manual_time_change_minutes"])
                        if raw.get("manual_time_change_minutes")
                        is not None
                        else None
                    ),
                    feedback_reason_codes=tuple(
                        str(value)
                        for value in raw.get(
                            "feedback_reason_codes",
                            [],
                        )
                    ),
                    unintended_effect_codes=tuple(
                        str(value)
                        for value in raw.get(
                            "unintended_effect_codes",
                            [],
                        )
                    ),
                    expert_interpretation=str(
                        raw.get("expert_interpretation", "")
                    ),
                    decision_taken=str(
                        raw.get("decision_taken", "")
                    ),
                    source_reference=str(
                        raw.get("source_reference", "")
                    ),
                    attestor_reference=str(
                        raw.get("attestor_reference", "")
                    ),
                    candidate_hash=str(
                        raw.get("candidate_hash", "")
                    ),
                    measurement_fingerprint=str(
                        raw.get("measurement_fingerprint", "")
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
            return MeasurementReviewPacket(
                packet_id=str(payload["packet_id"]),
                campaign_id=str(payload["campaign_id"]),
                measurement_program_id=str(
                    payload["measurement_program_id"]
                ),
                policy_id=str(payload["policy_id"]),
                policy_path=str(payload["policy_path"]),
                policy_hash=str(payload["policy_hash"]),
                candidate_path=str(payload["candidate_path"]),
                candidate_hash=str(payload["candidate_hash"]),
                theme=str(payload["theme"]),
                total_measurements=int(
                    payload["total_measurements"]
                ),
                eligible_measurements=int(
                    payload["eligible_measurements"]
                ),
                blocked_measurements=int(
                    payload["blocked_measurements"]
                ),
                taxonomy_status=str(
                    payload["taxonomy_status"]
                ),
                validation_log_import_allowed=bool(
                    payload["validation_log_import_allowed"]
                ),
                claim_boundary=str(payload["claim_boundary"]),
                items=tuple(items),
                created_at=str(payload["created_at"]),
                packet_hash=str(payload["packet_hash"]),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise OperationalMeasurementReviewError(
                "Measurement packet is missing required metadata"
            ) from exc

    @staticmethod
    def decision_template(
        packet: MeasurementReviewPacket,
    ) -> dict[str, Any]:
        return {
            "packet_id": packet.packet_id,
            "packet_hash": packet.packet_hash,
            "reviewer_reference": "",
            "instructions": (
                "Review each eligible operational measurement. "
                "APPROVE records a human-reviewed observational "
                "measurement only. It cannot enter the validation "
                "evidence log or change theme state."
            ),
            "validation_log_import_allowed": False,
            "decisions": [
                {
                    "review_id": item.review_id,
                    "measurement_id": item.measurement_id,
                    "pilot_id": item.pilot_id,
                    "metric_name": item.metric_name,
                    "comparison_method": item.comparison_method,
                    "outcome_before": item.outcome_before,
                    "outcome_after": item.outcome_after,
                    "effect_direction": item.effect_direction,
                    "effect_magnitude": item.effect_magnitude,
                    "persistence_period_days": (
                        item.persistence_period_days
                    ),
                    "known_confounders": list(
                        item.known_confounders
                    ),
                    "feedback_reason_codes": list(
                        item.feedback_reason_codes
                    ),
                    "unintended_effect_codes": list(
                        item.unintended_effect_codes
                    ),
                    "expert_interpretation": (
                        item.expert_interpretation
                    ),
                    "decision": "",
                    "reason": "",
                }
                for item in packet.items
                if item.eligibility
                is MeasurementEligibility.ELIGIBLE
            ],
            "blocked_items": [
                {
                    "review_id": item.review_id,
                    "measurement_id": item.measurement_id,
                    "blocking_reasons": list(
                        item.blocking_reasons
                    ),
                }
                for item in packet.items
                if item.eligibility
                is MeasurementEligibility.BLOCKED
            ],
        }

    @staticmethod
    def _item_payload(
        item: MeasurementReviewItem,
    ) -> dict[str, Any]:
        payload = asdict(item)
        payload["eligibility"] = item.eligibility.value
        payload["blocking_reasons"] = list(
            item.blocking_reasons
        )
        for key in (
            "operational_context_codes",
            "known_confounders",
            "feedback_reason_codes",
            "unintended_effect_codes",
        ):
            payload[key] = list(payload[key])
        return payload

    @staticmethod
    def _review_id(
        program_id: str,
        measurement_id: str,
        candidate_hash: str,
    ) -> str:
        material = (
            f"{program_id}|{measurement_id}|{candidate_hash}"
        ).encode()
        return (
            "OMRI-"
            + hashlib.sha256(material).hexdigest()[:20]
        )

    @staticmethod
    def _packet_id(
        program_id: str,
        candidate_hash: str,
        policy_hash: str,
    ) -> str:
        material = (
            f"{program_id}|{candidate_hash}|{policy_hash}"
        ).encode()
        return (
            "OMRP-"
            + hashlib.sha256(material).hexdigest()[:20]
        )

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
    def _load_object(path: Path) -> dict[str, Any]:
        try:
            payload = json.loads(
                path.read_text(encoding="utf-8")
            )
        except (OSError, json.JSONDecodeError) as exc:
            raise OperationalMeasurementReviewError(
                f"Could not read JSON object: {path}"
            ) from exc
        if not isinstance(payload, dict):
            raise OperationalMeasurementReviewError(
                "JSON file must contain an object"
            )
        return payload

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
            raise OperationalMeasurementReviewError(
                f"{label} must stay inside {self._project_path(root)}"
            )
        if resolved.suffix != suffix:
            raise OperationalMeasurementReviewError(
                f"{label} must use {suffix}"
            )
        if not resolved.is_file():
            raise OperationalMeasurementReviewError(
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
            raise OperationalMeasurementReviewError(
                f"{label} must stay inside {self._project_path(root)}"
            )
        if resolved.suffix != suffix:
            raise OperationalMeasurementReviewError(
                f"{label} must use {suffix}"
            )
        return resolved

    def _project_path(self, path: Path) -> str:
        try:
            return str(
                path.resolve().relative_to(self.project_root)
            )
        except ValueError as exc:
            raise OperationalMeasurementReviewError(
                "Path is outside the project root"
            ) from exc

    @staticmethod
    def _is_within(path: Path, root: Path) -> bool:
        try:
            path.relative_to(root)
            return True
        except ValueError:
            return False

    @staticmethod
    def _required_text(field_name: str, value: Any) -> str:
        if not isinstance(value, str) or not value.strip():
            raise OperationalMeasurementReviewError(
                f"{field_name} is required"
            )
        return " ".join(value.split())

    @classmethod
    def _audit_reference(
        cls,
        value: Any,
        *,
        field_name: str,
    ) -> str:
        reference = cls._required_text(field_name, value)
        if len(reference) > 120:
            raise OperationalMeasurementReviewError(
                f"{field_name} is too long"
            )
        if not TOKEN_PATTERN.fullmatch(reference):
            raise OperationalMeasurementReviewError(
                f"{field_name} contains unsupported characters"
            )
        return reference
