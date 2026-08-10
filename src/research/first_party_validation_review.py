"""Prepare and resolve Stage 4G first-party evidence reviews."""

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

from src.hermes.validation_evidence_log import ValidationEvidenceLog
from src.research.first_party_validation_storage import (
    ControlledJsonlStore,
    FirstPartyCandidateStore,
    FirstPartyDecisionStore,
    FirstPartyReviewPacketRegistry,
    FirstPartyVerifiedStore,
)


class FirstPartyReviewError(ValueError):
    """Raised when Stage 4G review preparation or resolution fails."""


class ReviewEligibility(StrEnum):
    ELIGIBLE = "eligible"
    HOLD_ONLY = "hold_only"
    BLOCKED = "blocked"


class ReviewDecision(StrEnum):
    APPROVE = "APPROVE"
    HOLD = "HOLD"
    REJECT = "REJECT"


TOKEN_PATTERN = re.compile(r"^[A-Za-z0-9_.:-]{3,120}$")


@dataclass(frozen=True)
class ReviewItem:
    review_id: str
    submission_id: str
    captured_at: str
    capture_reference: str
    participant_token: str
    participant_role: str
    capture_method: str
    evidence_kind: str
    evidence_type: str
    attestation_basis: str
    evidence_summary: str
    signal_strength: str
    supports_validation: bool
    source_reference: str
    consent_version: str
    question_set_version: str
    action_confirmed: bool
    measurement_count: int | None
    measurement_window: str
    candidate_hash: str
    response_fingerprint: str
    eligibility: ReviewEligibility
    blocking_reasons: tuple[str, ...] = ()


@dataclass(frozen=True)
class ReviewPacket:
    packet_id: str
    campaign_id: str
    policy_id: str
    policy_path: str
    policy_hash: str
    candidate_path: str
    candidate_hash: str
    target_log_path: str
    theme: str
    validation_plan_path: str
    total_candidates: int
    eligible_candidates: int
    hold_only_candidates: int
    blocked_candidates: int
    proposed_primary_entries: int
    proposed_risk_entries: int
    items: tuple[ReviewItem, ...]
    created_at: str
    packet_hash: str


@dataclass(frozen=True)
class ReviewResolution:
    resolution_id: str
    packet_id: str
    packet_hash: str
    campaign_id: str
    reviewer_reference: str
    approved: int
    held: int
    rejected: int
    blocked_by_gate: int
    verified_intake_path: str
    verified_intake_hash: str
    decision_registry_path: str
    resolved_at: str
    protected_actions: dict[str, bool] = field(
        default_factory=lambda: {
            "validation_evidence_log_modified": False,
            "theme_state_modified": False,
            "public_action_taken": False,
            "automatic_outreach": False,
        }
    )


class FirstPartyReviewService:
    """Prepare read-only review packets and resolve human decisions."""

    POLICY_VERSION = "STAGE4G-0.1"
    POLICY_ROOT = Path("config")
    PACKET_ROOT = Path(
        "reports/research/first_party_review_packets"
    )
    RESOLUTION_ROOT = Path(
        "reports/research/first_party_review_resolutions"
    )

    def __init__(
        self,
        *,
        candidate_store: FirstPartyCandidateStore | None = None,
        packet_registry: FirstPartyReviewPacketRegistry | None = None,
        decision_store: FirstPartyDecisionStore | None = None,
        verified_store: FirstPartyVerifiedStore | None = None,
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
            candidate_store or FirstPartyCandidateStore()
        )
        self.packet_registry = (
            packet_registry or FirstPartyReviewPacketRegistry()
        )
        self.decision_store = (
            decision_store or FirstPartyDecisionStore()
        )
        self.verified_store = (
            verified_store or FirstPartyVerifiedStore()
        )

    def prepare(
        self,
        *,
        candidate_file: str | Path,
        policy_file: str | Path,
        packet_output: str | Path,
        decision_template_output: str | Path,
    ) -> ReviewPacket:
        policy_path = self._controlled_file(
            Path(policy_file),
            root=self.policy_root,
            suffix=".json",
            label="campaign policy",
        )
        candidate_path = self._controlled_file(
            Path(candidate_file),
            root=self.candidate_store.root,
            suffix=".jsonl",
            label="candidate file",
        )
        packet_path = self._controlled_output(
            Path(packet_output),
            root=self.packet_root,
            suffix=".json",
            label="review packet",
        )
        template_path = self._controlled_output(
            Path(decision_template_output),
            root=self.packet_root,
            suffix=".json",
            label="decision template",
        )
        for path in (packet_path, template_path):
            if path.exists():
                raise FirstPartyReviewError(
                    f"Output already exists: {path}"
                )

        policy = self._load_object(policy_path)
        campaign_id = self._required_text(
            "campaign_id",
            policy.get("campaign_id", ""),
        )
        if candidate_path != self.candidate_store.path_for(
            campaign_id
        ):
            raise FirstPartyReviewError(
                "Candidate file does not match policy campaign"
            )
        candidates = self.candidate_store.read(candidate_path)
        if not candidates:
            raise FirstPartyReviewError(
                "Candidate file contains no records"
            )

        target_log_path = self._required_text(
            "target_log_path",
            policy.get("target_log_path", ""),
        )
        existing_references = {
            entry.source_reference
            for entry in ValidationEvidenceLog(
                log_path=target_log_path
            ).list_entries()
        }
        policy_hash = self._file_hash(policy_path)
        items: list[ReviewItem] = []
        for candidate in candidates:
            reasons = self._integrity_reasons(
                candidate,
                campaign_id=campaign_id,
                policy_hash=policy_hash,
            )
            evidence_type = str(
                candidate.get("evidence_type", "")
            )
            review_mode = str(
                candidate.get("review_mode", "")
            )
            submission_id = str(
                candidate.get("submission_id", "")
            )
            source_reference = (
                f"stage4g:{campaign_id}:{submission_id}"
            )
            if source_reference in existing_references:
                reasons.append(
                    "source_reference_already_in_validation_log"
                )
            if reasons:
                eligibility = ReviewEligibility.BLOCKED
            elif review_mode == "hold_only":
                eligibility = ReviewEligibility.HOLD_ONLY
            elif review_mode == "importable" and evidence_type:
                eligibility = ReviewEligibility.ELIGIBLE
            else:
                eligibility = ReviewEligibility.BLOCKED
                reasons.append("invalid_review_mode")

            items.append(
                ReviewItem(
                    review_id=self._review_id(
                        campaign_id,
                        submission_id,
                        str(candidate.get("candidate_hash", "")),
                    ),
                    submission_id=submission_id,
                    captured_at=str(
                        candidate.get("captured_at", "")
                    ),
                    capture_reference=str(
                        candidate.get("source_reference", "")
                    ),
                    participant_token=str(
                        candidate.get("participant_token", "")
                    ),
                    participant_role=str(
                        candidate.get("participant_role", "")
                    ),
                    capture_method=str(
                        candidate.get("capture_method", "")
                    ),
                    evidence_kind=str(
                        candidate.get("evidence_kind", "")
                    ),
                    evidence_type=evidence_type,
                    attestation_basis=str(
                        candidate.get("attestation_basis", "")
                    ),
                    evidence_summary=str(
                        candidate.get("evidence_summary", "")
                    ),
                    signal_strength=str(
                        candidate.get("signal_strength", "")
                    ),
                    supports_validation=bool(
                        candidate.get("supports_validation", False)
                    ),
                    source_reference=source_reference,
                    consent_version=str(
                        candidate.get("consent_version", "")
                    ),
                    question_set_version=str(
                        candidate.get("question_set_version", "")
                    ),
                    action_confirmed=bool(
                        candidate.get("action_confirmed", False)
                    ),
                    measurement_count=(
                        candidate.get("measurement_count")
                        if isinstance(
                            candidate.get("measurement_count"), int
                        )
                        and not isinstance(
                            candidate.get("measurement_count"), bool
                        )
                        else None
                    ),
                    measurement_window=str(
                        candidate.get("measurement_window", "")
                    ),
                    candidate_hash=str(
                        candidate.get("candidate_hash", "")
                    ),
                    response_fingerprint=str(
                        candidate.get("response_fingerprint", "")
                    ),
                    eligibility=eligibility,
                    blocking_reasons=tuple(dict.fromkeys(reasons)),
                )
            )

        candidate_hash = self._file_hash(candidate_path)
        packet_without_hash = {
            "packet_id": self._packet_id(
                campaign_id,
                candidate_hash,
                policy_hash,
            ),
            "campaign_id": campaign_id,
            "policy_id": self._required_text(
                "policy_id",
                policy.get("policy_id", ""),
            ),
            "policy_path": self._project_path(policy_path),
            "policy_hash": policy_hash,
            "candidate_path": self._project_path(candidate_path),
            "candidate_hash": candidate_hash,
            "target_log_path": target_log_path,
            "theme": self._required_text(
                "theme",
                policy.get("theme", ""),
            ),
            "validation_plan_path": self._required_text(
                "validation_plan_path",
                policy.get("validation_plan_path", ""),
            ),
            "total_candidates": len(items),
            "eligible_candidates": sum(
                item.eligibility is ReviewEligibility.ELIGIBLE
                for item in items
            ),
            "hold_only_candidates": sum(
                item.eligibility is ReviewEligibility.HOLD_ONLY
                for item in items
            ),
            "blocked_candidates": sum(
                item.eligibility is ReviewEligibility.BLOCKED
                for item in items
            ),
            "proposed_primary_entries": sum(
                item.eligibility is ReviewEligibility.ELIGIBLE
                and item.evidence_type
                in ValidationEvidenceLog.PRIMARY_EVIDENCE_TYPES
                for item in items
            ),
            "proposed_risk_entries": sum(
                item.eligibility is ReviewEligibility.ELIGIBLE
                and item.evidence_type == "risk_finding"
                for item in items
            ),
            "items": [
                self._item_payload(item) for item in items
            ],
            "created_at": datetime.now(UTC).isoformat(),
        }
        packet_hash = self._payload_hash(packet_without_hash)
        packet_metadata = dict(packet_without_hash)
        packet_metadata.pop("items")
        packet = ReviewPacket(
            **packet_metadata,
            items=tuple(items),
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
                    "packet_path": self._project_path(packet_path),
                    "template_path": self._project_path(
                        template_path
                    ),
                    "created_at": packet.created_at,
                }
            ],
        )
        return packet

    def resolve(
        self,
        *,
        packet_file: str | Path,
        decision_file: str | Path,
        output_file: str | Path,
    ) -> ReviewResolution:
        packet_path = self._controlled_file(
            Path(packet_file),
            root=self.packet_root,
            suffix=".json",
            label="review packet",
        )
        decision_path = self._controlled_file(
            Path(decision_file),
            root=self.packet_root,
            suffix=".json",
            label="review decision",
        )
        output_path = self._controlled_output(
            Path(output_file),
            root=self.resolution_root,
            suffix=".json",
            label="review resolution",
        )
        if output_path.exists():
            raise FirstPartyReviewError(
                "Review resolution already exists"
            )

        packet = self.packet_from_payload(
            self._load_object(packet_path)
        )
        self._verify_packet(packet, packet_path)
        if self.decision_store.has_packet(packet.packet_id):
            raise FirstPartyReviewError(
                "Review packet has already been resolved"
            )
        reviewer_reference, decisions = self._parse_decisions(
            packet,
            self._load_object(decision_path),
        )

        resolution_id = "FPVR-" + uuid4().hex
        item_by_id = {
            item.review_id: item for item in packet.items
        }
        approved_items = [
            item_by_id[review_id]
            for review_id, value in decisions.items()
            if value["decision"] is ReviewDecision.APPROVE
        ]
        held = sum(
            value["decision"] is ReviewDecision.HOLD
            for value in decisions.values()
        )
        rejected = sum(
            value["decision"] is ReviewDecision.REJECT
            for value in decisions.values()
        )

        verified_path = self.verified_store.path_for(
            resolution_id
        )
        decision_registry_path = self.decision_store.path_for(
            packet.campaign_id
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
                "review_id": review_id,
                "reviewer_reference": reviewer_reference,
                "decision": value["decision"].value,
                "reason": value["reason"],
                "resolved_at": datetime.now(UTC).isoformat(),
            }
            for review_id, value in decisions.items()
        ]

        verified_snapshot = ControlledJsonlStore.snapshot(
            verified_path
        )
        decision_snapshot = ControlledJsonlStore.snapshot(
            decision_registry_path
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
                decision_registry_path,
                decision_records,
            )
            resolution = ReviewResolution(
                resolution_id=resolution_id,
                packet_id=packet.packet_id,
                packet_hash=packet.packet_hash,
                campaign_id=packet.campaign_id,
                reviewer_reference=reviewer_reference,
                approved=len(approved_items),
                held=held,
                rejected=rejected,
                blocked_by_gate=packet.blocked_candidates,
                verified_intake_path=self._project_path(
                    verified_path
                ),
                verified_intake_hash=self._file_hash(
                    verified_path
                ),
                decision_registry_path=self._project_path(
                    decision_registry_path
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
            ControlledJsonlStore.restore(
                verified_path,
                verified_snapshot,
            )
            ControlledJsonlStore.restore(
                decision_registry_path,
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
        policy_hash: str,
    ) -> list[str]:
        reasons: list[str] = []
        if str(candidate.get("campaign_id", "")) != campaign_id:
            reasons.append("campaign_id_mismatch")
        if str(candidate.get("policy_hash", "")) != policy_hash:
            reasons.append("policy_hash_mismatch")
        supplied_hash = str(candidate.get("candidate_hash", ""))
        payload = dict(candidate)
        payload.pop("candidate_hash", None)
        if self._payload_hash(payload) != supplied_hash:
            reasons.append("candidate_hash_mismatch")
        if str(candidate.get("schema_version", "")) != (
            self.POLICY_VERSION
        ):
            reasons.append("schema_version_mismatch")
        return reasons

    def _parse_decisions(
        self,
        packet: ReviewPacket,
        payload: dict[str, Any],
    ) -> tuple[str, dict[str, dict[str, Any]]]:
        if str(payload.get("packet_id", "")) != packet.packet_id:
            raise FirstPartyReviewError(
                "Decision packet_id does not match"
            )
        if str(payload.get("packet_hash", "")) != packet.packet_hash:
            raise FirstPartyReviewError(
                "Decision packet_hash does not match"
            )
        reviewer_reference = self._audit_reference(
            payload.get("reviewer_reference", ""),
            "reviewer_reference",
        )
        raw_decisions = payload.get("decisions")
        if not isinstance(raw_decisions, list):
            raise FirstPartyReviewError(
                "Review decisions must be a list"
            )
        reviewable = {
            item.review_id: item
            for item in packet.items
            if item.eligibility
            in {
                ReviewEligibility.ELIGIBLE,
                ReviewEligibility.HOLD_ONLY,
            }
        }
        decisions: dict[str, dict[str, Any]] = {}
        for raw in raw_decisions:
            if not isinstance(raw, dict):
                raise FirstPartyReviewError(
                    "Every review decision must be an object"
                )
            review_id = self._required_text(
                "review_id",
                raw.get("review_id", ""),
            )
            if review_id in decisions:
                raise FirstPartyReviewError(
                    f"Duplicate review decision: {review_id}"
                )
            item = reviewable.get(review_id)
            if item is None:
                raise FirstPartyReviewError(
                    "Decision references blocked or unknown item"
                )
            try:
                decision = ReviewDecision(
                    self._required_text(
                        "decision",
                        raw.get("decision", ""),
                    ).upper()
                )
            except ValueError as exc:
                raise FirstPartyReviewError(
                    "Decision must be APPROVE, HOLD, or REJECT"
                ) from exc
            reason = self._required_text(
                "reason",
                raw.get("reason", ""),
            )
            if (
                item.eligibility is ReviewEligibility.HOLD_ONLY
                and decision is ReviewDecision.APPROVE
            ):
                raise FirstPartyReviewError(
                    "A hold-only taxonomy-gap item cannot be approved"
                )
            decisions[review_id] = {
                "decision": decision,
                "reason": reason,
            }
        missing = sorted(set(reviewable) - set(decisions))
        if missing:
            raise FirstPartyReviewError(
                "Every reviewable item requires a decision. "
                f"Missing: {missing}"
            )
        return reviewer_reference, decisions

    @staticmethod
    def _verified_record(
        packet: ReviewPacket,
        item: ReviewItem,
        *,
        resolution_id: str,
        reviewer_reference: str,
        reason: str,
    ) -> dict[str, Any]:
        if item.eligibility is not ReviewEligibility.ELIGIBLE:
            raise FirstPartyReviewError(
                "Only eligible items can enter verified intake"
            )
        return {
            "schema_version": "STAGE4G-0.1",
            "resolution_id": resolution_id,
            "packet_id": packet.packet_id,
            "packet_hash": packet.packet_hash,
            "campaign_id": packet.campaign_id,
            "review_id": item.review_id,
            "submission_id": item.submission_id,
            "captured_at": item.captured_at,
            "capture_reference": item.capture_reference,
            "reviewer_reference": reviewer_reference,
            "decision": ReviewDecision.APPROVE.value,
            "decision_reason": reason,
            "theme": packet.theme,
            "validation_plan_path": packet.validation_plan_path,
            "target_log_path": packet.target_log_path,
            "evidence_type": item.evidence_type,
            "evidence_summary": item.evidence_summary,
            "source_reference": item.source_reference,
            "signal_strength": item.signal_strength,
            "supports_validation": item.supports_validation,
            "source_trust": (
                ValidationEvidenceLog.HUMAN_ATTESTED_FIRST_PARTY
            ),
            "participant_token": item.participant_token,
            "participant_role": item.participant_role,
            "capture_method": item.capture_method,
            "evidence_kind": item.evidence_kind,
            "attestation_basis": item.attestation_basis,
            "consent_version": item.consent_version,
            "question_set_version": item.question_set_version,
            "action_confirmed": item.action_confirmed,
            "measurement_count": item.measurement_count,
            "measurement_window": item.measurement_window,
            "candidate_hash": item.candidate_hash,
            "response_fingerprint": item.response_fingerprint,
            "verified_at": datetime.now(UTC).isoformat(),
        }

    def _verify_packet(
        self,
        packet: ReviewPacket,
        packet_path: Path,
    ) -> None:
        candidate_path = (
            self.project_root / packet.candidate_path
        ).resolve()
        policy_path = (
            self.project_root / packet.policy_path
        ).resolve()
        if self._file_hash(candidate_path) != packet.candidate_hash:
            raise FirstPartyReviewError(
                "Candidate file changed after packet preparation"
            )
        if self._file_hash(policy_path) != packet.policy_hash:
            raise FirstPartyReviewError(
                "Campaign policy changed after packet preparation"
            )
        payload = self.packet_payload(packet)
        supplied_hash = payload.pop("packet_hash")
        if self._payload_hash(payload) != supplied_hash:
            raise FirstPartyReviewError(
                "Review packet hash verification failed"
            )
        registered = self.packet_registry.find(packet.packet_id)
        if registered is None:
            raise FirstPartyReviewError(
                "Review packet is not registered"
            )
        if registered["packet_hash"] != packet.packet_hash:
            raise FirstPartyReviewError(
                "Registered packet hash does not match"
            )
        if registered["packet_path"] != self._project_path(
            packet_path
        ):
            raise FirstPartyReviewError(
                "Registered packet path does not match"
            )

    @staticmethod
    def packet_payload(packet: ReviewPacket) -> dict[str, Any]:
        payload = asdict(packet)
        payload["items"] = [
            FirstPartyReviewService._item_payload(item)
            for item in packet.items
        ]
        return payload

    @classmethod
    def packet_from_payload(
        cls,
        payload: dict[str, Any],
    ) -> ReviewPacket:
        raw_items = payload.get("items")
        if not isinstance(raw_items, list):
            raise FirstPartyReviewError(
                "Review packet items must be a list"
            )
        items: list[ReviewItem] = []
        for raw in raw_items:
            if not isinstance(raw, dict):
                raise FirstPartyReviewError(
                    "Review packet item must be an object"
                )
            try:
                eligibility = ReviewEligibility(
                    str(raw["eligibility"])
                )
            except (KeyError, ValueError) as exc:
                raise FirstPartyReviewError(
                    "Review packet item has invalid eligibility"
                ) from exc
            items.append(
                ReviewItem(
                    review_id=str(raw.get("review_id", "")),
                    submission_id=str(
                        raw.get("submission_id", "")
                    ),
                    captured_at=str(raw.get("captured_at", "")),
                    capture_reference=str(
                        raw.get("capture_reference", "")
                    ),
                    participant_token=str(
                        raw.get("participant_token", "")
                    ),
                    participant_role=str(
                        raw.get("participant_role", "")
                    ),
                    capture_method=str(
                        raw.get("capture_method", "")
                    ),
                    evidence_kind=str(
                        raw.get("evidence_kind", "")
                    ),
                    evidence_type=str(
                        raw.get("evidence_type", "")
                    ),
                    attestation_basis=str(
                        raw.get("attestation_basis", "")
                    ),
                    evidence_summary=str(
                        raw.get("evidence_summary", "")
                    ),
                    signal_strength=str(
                        raw.get("signal_strength", "")
                    ),
                    supports_validation=bool(
                        raw.get("supports_validation", False)
                    ),
                    source_reference=str(
                        raw.get("source_reference", "")
                    ),
                    consent_version=str(
                        raw.get("consent_version", "")
                    ),
                    question_set_version=str(
                        raw.get("question_set_version", "")
                    ),
                    action_confirmed=bool(
                        raw.get("action_confirmed", False)
                    ),
                    measurement_count=(
                        raw.get("measurement_count")
                        if isinstance(raw.get("measurement_count"), int)
                        and not isinstance(
                            raw.get("measurement_count"), bool
                        )
                        else None
                    ),
                    measurement_window=str(
                        raw.get("measurement_window", "")
                    ),
                    candidate_hash=str(
                        raw.get("candidate_hash", "")
                    ),
                    response_fingerprint=str(
                        raw.get("response_fingerprint", "")
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
            return ReviewPacket(
                packet_id=str(payload["packet_id"]),
                campaign_id=str(payload["campaign_id"]),
                policy_id=str(payload["policy_id"]),
                policy_path=str(payload["policy_path"]),
                policy_hash=str(payload["policy_hash"]),
                candidate_path=str(payload["candidate_path"]),
                candidate_hash=str(payload["candidate_hash"]),
                target_log_path=str(payload["target_log_path"]),
                theme=str(payload["theme"]),
                validation_plan_path=str(
                    payload["validation_plan_path"]
                ),
                total_candidates=int(payload["total_candidates"]),
                eligible_candidates=int(
                    payload["eligible_candidates"]
                ),
                hold_only_candidates=int(
                    payload["hold_only_candidates"]
                ),
                blocked_candidates=int(
                    payload["blocked_candidates"]
                ),
                proposed_primary_entries=int(
                    payload["proposed_primary_entries"]
                ),
                proposed_risk_entries=int(
                    payload["proposed_risk_entries"]
                ),
                items=tuple(items),
                created_at=str(payload["created_at"]),
                packet_hash=str(payload["packet_hash"]),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise FirstPartyReviewError(
                "Review packet is missing required metadata"
            ) from exc

    @staticmethod
    def decision_template(packet: ReviewPacket) -> dict[str, Any]:
        return {
            "packet_id": packet.packet_id,
            "packet_hash": packet.packet_hash,
            "reviewer_reference": "",
            "instructions": (
                "Decide every eligible or hold-only item. APPROVE "
                "promotes an eligible item only to verified intake. "
                "Hold-only taxonomy-gap responses cannot be approved."
            ),
            "decisions": [
                {
                    "review_id": item.review_id,
                    "submission_id": item.submission_id,
                    "captured_at": item.captured_at,
                    "capture_reference": item.capture_reference,
                    "participant_role": item.participant_role,
                    "capture_method": item.capture_method,
                    "evidence_kind": item.evidence_kind,
                    "evidence_type": item.evidence_type,
                    "eligibility": item.eligibility.value,
                    "evidence_summary": item.evidence_summary,
                    "signal_strength": item.signal_strength,
                    "supports_validation": item.supports_validation,
                    "action_confirmed": item.action_confirmed,
                    "measurement_count": item.measurement_count,
                    "measurement_window": item.measurement_window,
                    "decision": "",
                    "reason": "",
                }
                for item in packet.items
                if item.eligibility
                in {
                    ReviewEligibility.ELIGIBLE,
                    ReviewEligibility.HOLD_ONLY,
                }
            ],
            "blocked_items": [
                {
                    "review_id": item.review_id,
                    "submission_id": item.submission_id,
                    "blocking_reasons": list(
                        item.blocking_reasons
                    ),
                }
                for item in packet.items
                if item.eligibility is ReviewEligibility.BLOCKED
            ],
        }

    @staticmethod
    def _item_payload(item: ReviewItem) -> dict[str, Any]:
        return {
            **asdict(item),
            "eligibility": item.eligibility.value,
            "blocking_reasons": list(item.blocking_reasons),
        }

    @staticmethod
    def _review_id(
        campaign_id: str,
        submission_id: str,
        candidate_hash: str,
    ) -> str:
        material = (
            f"{campaign_id}|{submission_id}|{candidate_hash}"
        ).encode()
        return "FPVRI-" + hashlib.sha256(material).hexdigest()[:20]

    @staticmethod
    def _packet_id(
        campaign_id: str,
        candidate_hash: str,
        policy_hash: str,
    ) -> str:
        material = (
            f"{campaign_id}|{candidate_hash}|{policy_hash}"
        ).encode()
        return "FPVP-" + hashlib.sha256(material).hexdigest()[:20]

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
            for chunk in iter(lambda: handle.read(65_536), b""):
                digest.update(chunk)
        return digest.hexdigest()

    @staticmethod
    def _load_object(path: Path) -> dict[str, Any]:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise FirstPartyReviewError(
                f"Could not read JSON object: {path}"
            ) from exc
        if not isinstance(payload, dict):
            raise FirstPartyReviewError(
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
            raise FirstPartyReviewError(
                f"{label} must stay inside {self._project_path(root)}"
            )
        if resolved.suffix != suffix or not resolved.is_file():
            raise FirstPartyReviewError(
                f"{label} must be an existing {suffix} file"
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
            raise FirstPartyReviewError(
                f"{label} must stay inside {self._project_path(root)}"
            )
        if resolved.suffix != suffix:
            raise FirstPartyReviewError(
                f"{label} must use {suffix}"
            )
        return resolved

    def _project_path(self, path: Path) -> str:
        try:
            return str(path.resolve().relative_to(self.project_root))
        except ValueError as exc:
            raise FirstPartyReviewError(
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
            raise FirstPartyReviewError(
                f"{field_name} is required"
            )
        return " ".join(value.split())

    @classmethod
    def _audit_reference(
        cls,
        value: Any,
        field_name: str,
    ) -> str:
        reference = cls._required_text(field_name, value)
        if not TOKEN_PATTERN.fullmatch(reference):
            raise FirstPartyReviewError(
                f"{field_name} contains unsupported characters"
            )
        return reference
