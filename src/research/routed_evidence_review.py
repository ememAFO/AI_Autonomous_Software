"""Stage 4E review and promotion gate for routed research evidence.

This module reviews unapproved Stage 4D candidates. It can promote a
human-approved candidate only into a verified-intake queue. It cannot modify
the approved evidence registry, validation evidence log, theme state, public
content, or outreach systems.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit
from uuid import uuid4

from src.research.routed_evidence_review_storage import (
    EvidenceReviewDecisionRegistry,
    EvidenceReviewPacketRegistry,
    VerifiedEvidenceIntakeQueue,
)


class RoutedEvidenceReviewError(ValueError):
    """Raised when candidate review or promotion violates Stage 4E policy."""


class ReviewEligibility(StrEnum):
    ELIGIBLE = "eligible"
    BLOCKED = "blocked"


class HumanEvidenceDecision(StrEnum):
    APPROVE = "APPROVE"
    REJECT = "REJECT"
    HOLD = "HOLD"


ALLOWED_CLASSIFICATIONS = frozenset(
    {
        "source-verified",
        "triangulated",
        "observed",
        "inferred",
        "illustrative",
        "contested",
        "rejected",
    }
)
ALLOWED_APPROVAL_CLASSIFICATIONS = (
    ALLOWED_CLASSIFICATIONS - {"rejected"}
)
ALLOWED_SIGNAL_STRENGTHS = frozenset(
    {"strong", "medium", "weak", "negative"}
)
ALLOWED_FETCHERS = frozenset({"http", "supplied_public_post"})
REQUIRED_CANDIDATE_FIELDS = frozenset(
    {
        "workflow_id",
        "source_id",
        "adapter_name",
        "adapter_version",
        "requested_url",
        "final_url",
        "canonical_url",
        "title",
        "retrieved_at",
        "status",
        "content_ok",
        "content",
        "content_hash",
        "fetcher_used",
        "cached",
    }
)


@dataclass(frozen=True)
class CandidateReviewItem:
    review_id: str
    candidate_index: int
    workflow_id: str
    source_id: str
    adapter_name: str
    adapter_version: str
    requested_url: str
    final_url: str
    canonical_url: str
    normalized_canonical_url: str
    title: str
    publisher_or_domain: str
    retrieved_at: str
    status: str
    content_ok: bool
    content_hash: str
    fetcher_used: str
    cached: bool
    source_type_hint: str
    official_hint: bool
    published_date_hint: str
    warnings: tuple[str, ...]
    eligibility: ReviewEligibility
    blocking_reasons: tuple[str, ...] = ()
    duplicate_of_review_id: str = ""


@dataclass(frozen=True)
class EvidenceReviewPacket:
    packet_id: str
    workflow_id: str
    candidate_file: str
    candidate_file_hash: str
    total_candidates: int
    eligible_candidates: int
    blocked_candidates: int
    duplicate_candidates: int
    items: tuple[CandidateReviewItem, ...]
    policy_version: str
    created_at: str
    packet_hash: str


@dataclass(frozen=True)
class ReviewDecisionInput:
    review_id: str
    decision: HumanEvidenceDecision
    reason: str
    evidence_summary: str = ""
    classification: str = ""
    signal_strength: str = ""
    supports_validation: bool | None = None


@dataclass(frozen=True)
class EvidenceReviewResolution:
    resolution_id: str
    packet_id: str
    packet_hash: str
    workflow_id: str
    reviewer_reference: str
    approved: int
    rejected: int
    held: int
    blocked_by_gate: int
    verified_intake_path: str
    decision_registry_path: str
    resolved_at: str
    protected_actions: dict[str, bool] = field(
        default_factory=lambda: {
            "approved_registry_modified": False,
            "validation_evidence_log_modified": False,
            "theme_state_modified": False,
            "public_action_taken": False,
            "automatic_outreach": False,
        }
    )


class RoutedEvidenceReviewService:
    """Prepare immutable review packets and resolve explicit human decisions."""

    DEFAULT_CANDIDATE_ROOT = Path("data/research/evidence_candidates")
    DEFAULT_PACKET_ROOT = Path(
        "reports/research/evidence_review_packets"
    )
    DEFAULT_RESOLUTION_ROOT = Path(
        "reports/research/evidence_review_resolutions"
    )
    POLICY_VERSION = "STAGE4E-0.1"

    def __init__(
        self,
        *,
        packet_registry: EvidenceReviewPacketRegistry | None = None,
        decision_registry: EvidenceReviewDecisionRegistry | None = None,
        verified_queue: VerifiedEvidenceIntakeQueue | None = None,
    ) -> None:
        self.project_root = Path.cwd().resolve()
        self.candidate_root = (
            self.project_root / self.DEFAULT_CANDIDATE_ROOT
        ).resolve()
        self.packet_root = (
            self.project_root / self.DEFAULT_PACKET_ROOT
        ).resolve()
        self.resolution_root = (
            self.project_root / self.DEFAULT_RESOLUTION_ROOT
        ).resolve()
        self.packet_registry = (
            packet_registry or EvidenceReviewPacketRegistry()
        )
        self.decision_registry = (
            decision_registry or EvidenceReviewDecisionRegistry()
        )
        self.verified_queue = (
            verified_queue or VerifiedEvidenceIntakeQueue()
        )

    def prepare_packet(
        self,
        *,
        workflow_id: str,
        candidate_file: str | Path,
        output_json: str | Path,
        output_markdown: str | Path,
        decision_template: str | Path,
    ) -> EvidenceReviewPacket:
        workflow_id = self._required_text(
            "workflow_id",
            workflow_id,
        )
        candidate_path = self._validate_candidate_path(
            Path(candidate_file)
        )
        json_path = self._validate_report_path(
            Path(output_json),
            root=self.packet_root,
            suffix=".json",
            label="review packet JSON",
        )
        markdown_path = self._validate_report_path(
            Path(output_markdown),
            root=self.packet_root,
            suffix=".md",
            label="review packet Markdown",
        )
        template_path = self._validate_report_path(
            Path(decision_template),
            root=self.packet_root,
            suffix=".json",
            label="review decision template",
        )

        records = self._load_candidate_records(candidate_path)
        items = self._review_items(
            workflow_id=workflow_id,
            records=records,
        )
        candidate_file_hash = self._file_hash(candidate_path)
        created_at = datetime.now(UTC).isoformat()
        packet_id = (
            "ERP-"
            + self._safe_component(workflow_id)[:70]
            + "-"
            + uuid4().hex[:12]
        )
        packet_without_hash = {
            "packet_id": packet_id,
            "workflow_id": workflow_id,
            "candidate_file": self._project_path(candidate_path),
            "candidate_file_hash": candidate_file_hash,
            "total_candidates": len(items),
            "eligible_candidates": sum(
                item.eligibility is ReviewEligibility.ELIGIBLE
                for item in items
            ),
            "blocked_candidates": sum(
                item.eligibility is ReviewEligibility.BLOCKED
                for item in items
            ),
            "duplicate_candidates": sum(
                bool(item.duplicate_of_review_id)
                for item in items
            ),
            "items": [
                self._item_payload(item)
                for item in items
            ],
            "policy_version": self.POLICY_VERSION,
            "created_at": created_at,
        }
        packet_hash = self._payload_hash(packet_without_hash)
        packet = EvidenceReviewPacket(
            packet_id=packet_id,
            workflow_id=workflow_id,
            candidate_file=self._project_path(candidate_path),
            candidate_file_hash=candidate_file_hash,
            total_candidates=len(items),
            eligible_candidates=packet_without_hash[
                "eligible_candidates"
            ],
            blocked_candidates=packet_without_hash[
                "blocked_candidates"
            ],
            duplicate_candidates=packet_without_hash[
                "duplicate_candidates"
            ],
            items=tuple(items),
            policy_version=self.POLICY_VERSION,
            created_at=created_at,
            packet_hash=packet_hash,
        )

        json_path.parent.mkdir(parents=True, exist_ok=True)
        json_path.write_text(
            json.dumps(
                self.packet_payload(packet),
                indent=2,
                ensure_ascii=False,
            )
            + "\n",
            encoding="utf-8",
        )
        markdown_path.write_text(
            self.format_markdown(packet),
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
        self.packet_registry.append(
            packet=packet,
            packet_json_path=self._project_path(json_path),
            packet_markdown_path=self._project_path(markdown_path),
            decision_template_path=self._project_path(template_path),
        )
        return packet

    def resolve(
        self,
        *,
        packet_file: str | Path,
        decision_file: str | Path,
        output_path: str | Path,
    ) -> EvidenceReviewResolution:
        packet_path = self._validate_report_path(
            Path(packet_file),
            root=self.packet_root,
            suffix=".json",
            label="review packet JSON",
            must_exist=True,
        )
        decision_path = self._validate_report_path(
            Path(decision_file),
            root=self.packet_root,
            suffix=".json",
            label="review decision file",
            must_exist=True,
        )
        resolution_path = self._validate_report_path(
            Path(output_path),
            root=self.resolution_root,
            suffix=".json",
            label="review resolution report",
        )

        packet_data = self._load_json_object(packet_path)
        packet = self.packet_from_payload(packet_data)
        self._verify_packet_integrity(
            packet=packet,
            packet_path=packet_path,
        )
        decisions_data = self._load_json_object(decision_path)
        reviewer_reference, decisions = (
            self._parse_decisions(
                packet=packet,
                payload=decisions_data,
            )
        )
        if self.decision_registry.has_packet(packet.packet_id):
            raise RoutedEvidenceReviewError(
                "Review packet has already been resolved"
            )

        item_by_review_id = {
            item.review_id: item
            for item in packet.items
        }
        candidate_records = self._load_candidate_records(
            self.project_root / packet.candidate_file
        )
        record_by_source_id = {
            str(record.get("source_id", "")): record
            for record in candidate_records
        }

        approved = 0
        rejected = 0
        held = 0
        verified_paths: list[str] = []
        resolved_at = datetime.now(UTC).isoformat()
        resolution_id = "ERR-" + uuid4().hex

        for decision in decisions:
            item = item_by_review_id[decision.review_id]
            self._validate_decision_for_item(
                item=item,
                decision=decision,
            )
            if decision.decision is HumanEvidenceDecision.APPROVE:
                record = record_by_source_id.get(item.source_id)
                if record is None:
                    raise RoutedEvidenceReviewError(
                        "Candidate source record disappeared before "
                        f"promotion: {item.source_id}"
                    )
                verified_path = self.verified_queue.append(
                    {
                        "resolution_id": resolution_id,
                        "packet_id": packet.packet_id,
                        "packet_hash": packet.packet_hash,
                        "workflow_id": packet.workflow_id,
                        "review_id": item.review_id,
                        "source_id": item.source_id,
                        "reviewer_reference": reviewer_reference,
                        "decision": decision.decision.value,
                        "decision_reason": decision.reason,
                        "evidence_summary": decision.evidence_summary,
                        "classification": decision.classification,
                        "signal_strength": decision.signal_strength,
                        "supports_validation": (
                            decision.supports_validation
                        ),
                        "canonical_url": item.canonical_url,
                        "title": item.title,
                        "adapter_name": item.adapter_name,
                        "adapter_version": item.adapter_version,
                        "retrieved_at": item.retrieved_at,
                        "content_hash": item.content_hash,
                        "candidate_queue_reference": (
                            packet.candidate_file
                        ),
                        "source_type_hint": item.source_type_hint,
                        "official_hint": item.official_hint,
                        "published_date_hint": (
                            item.published_date_hint
                        ),
                        "verified_at": resolved_at,
                    }
                )
                verified_paths.append(str(verified_path))
                approved += 1
            elif decision.decision is HumanEvidenceDecision.REJECT:
                rejected += 1
            else:
                held += 1

            self.decision_registry.append(
                {
                    "resolution_id": resolution_id,
                    "packet_id": packet.packet_id,
                    "packet_hash": packet.packet_hash,
                    "workflow_id": packet.workflow_id,
                    "review_id": item.review_id,
                    "source_id": item.source_id,
                    "reviewer_reference": reviewer_reference,
                    "decision": decision.decision.value,
                    "reason": decision.reason,
                    "evidence_summary": decision.evidence_summary,
                    "classification": decision.classification,
                    "signal_strength": decision.signal_strength,
                    "supports_validation": (
                        decision.supports_validation
                    ),
                    "resolved_at": resolved_at,
                }
            )

        blocked_by_gate = sum(
            item.eligibility is ReviewEligibility.BLOCKED
            for item in packet.items
        )
        resolution = EvidenceReviewResolution(
            resolution_id=resolution_id,
            packet_id=packet.packet_id,
            packet_hash=packet.packet_hash,
            workflow_id=packet.workflow_id,
            reviewer_reference=reviewer_reference,
            approved=approved,
            rejected=rejected,
            held=held,
            blocked_by_gate=blocked_by_gate,
            verified_intake_path=(
                verified_paths[0] if verified_paths else ""
            ),
            decision_registry_path=str(
                self.decision_registry.path_for(
                    packet.workflow_id
                )
            ),
            resolved_at=resolved_at,
        )
        resolution_path.parent.mkdir(parents=True, exist_ok=True)
        resolution_path.write_text(
            json.dumps(
                asdict(resolution),
                indent=2,
                ensure_ascii=False,
            )
            + "\n",
            encoding="utf-8",
        )
        return resolution

    def _review_items(
        self,
        *,
        workflow_id: str,
        records: list[dict[str, Any]],
    ) -> list[CandidateReviewItem]:
        items: list[CandidateReviewItem] = []
        canonical_owners: dict[str, str] = {}
        content_owners: dict[str, str] = {}
        source_ids: set[str] = set()

        for index, record in enumerate(records, start=1):
            reasons = self._candidate_blocking_reasons(
                workflow_id=workflow_id,
                record=record,
            )
            source_id = str(record.get("source_id", "")).strip()
            canonical_url = str(
                record.get("canonical_url", "")
            ).strip()
            normalized_url = self._normalize_url(
                canonical_url
            )
            content_hash = str(
                record.get("content_hash", "")
            ).strip().lower()
            review_id = self._review_id(
                workflow_id=workflow_id,
                source_id=source_id or f"record-{index}",
                normalized_url=normalized_url,
                content_hash=content_hash,
            )
            duplicate_of = ""

            if source_id in source_ids:
                reasons.append("duplicate_source_id")
            elif source_id:
                source_ids.add(source_id)

            if normalized_url and normalized_url in canonical_owners:
                duplicate_of = canonical_owners[normalized_url]
                reasons.append("duplicate_canonical_url")
            elif normalized_url:
                canonical_owners[normalized_url] = review_id

            if content_hash and content_hash in content_owners:
                duplicate_of = (
                    duplicate_of or content_owners[content_hash]
                )
                reasons.append("duplicate_content_hash")
            elif content_hash:
                content_owners[content_hash] = review_id

            warnings = self._warnings(record.get("warnings", []))
            item = CandidateReviewItem(
                review_id=review_id,
                candidate_index=index,
                workflow_id=str(
                    record.get("workflow_id", "")
                ),
                source_id=source_id,
                adapter_name=str(
                    record.get("adapter_name", "")
                ),
                adapter_version=str(
                    record.get("adapter_version", "")
                ),
                requested_url=str(
                    record.get("requested_url", "")
                ),
                final_url=str(record.get("final_url", "")),
                canonical_url=canonical_url,
                normalized_canonical_url=normalized_url,
                title=str(record.get("title", "")),
                publisher_or_domain=str(
                    record.get("publisher_or_domain", "")
                ),
                retrieved_at=str(
                    record.get("retrieved_at", "")
                ),
                status=str(record.get("status", "")),
                content_ok=bool(record.get("content_ok", False)),
                content_hash=content_hash,
                fetcher_used=str(
                    record.get("fetcher_used", "")
                ),
                cached=bool(record.get("cached", False)),
                source_type_hint=str(
                    record.get("source_type_hint", "")
                ),
                official_hint=bool(
                    record.get("official_hint", False)
                ),
                published_date_hint=str(
                    record.get("published_date_hint", "")
                ),
                warnings=warnings,
                eligibility=(
                    ReviewEligibility.BLOCKED
                    if reasons
                    else ReviewEligibility.ELIGIBLE
                ),
                blocking_reasons=tuple(dict.fromkeys(reasons)),
                duplicate_of_review_id=duplicate_of,
            )
            items.append(item)
        return items

    def _candidate_blocking_reasons(
        self,
        *,
        workflow_id: str,
        record: dict[str, Any],
    ) -> list[str]:
        reasons: list[str] = []
        missing = sorted(
            field
            for field in REQUIRED_CANDIDATE_FIELDS
            if field not in record
        )
        if missing:
            reasons.append(
                "missing_fields:" + ",".join(missing)
            )
        if str(record.get("workflow_id", "")) != workflow_id:
            reasons.append("workflow_id_mismatch")
        if not str(record.get("source_id", "")).strip():
            reasons.append("source_id_missing")
        if str(record.get("status", "")).lower() != "candidate":
            reasons.append("candidate_status_not_reviewable")
        if record.get("content_ok") is not True:
            reasons.append("content_not_ok")
        if record.get("cached") is not False:
            reasons.append("cached_content_not_allowed")
        fetcher = str(record.get("fetcher_used", ""))
        if fetcher not in ALLOWED_FETCHERS:
            reasons.append("fetcher_not_approved")
        for name in (
            "adapter_name",
            "adapter_version",
            "title",
            "retrieved_at",
            "content_hash",
        ):
            if not str(record.get(name, "")).strip():
                reasons.append(f"{name}_missing")
        for url_field in (
            "requested_url",
            "final_url",
            "canonical_url",
        ):
            if not self._valid_public_url(
                str(record.get(url_field, ""))
            ):
                reasons.append(f"{url_field}_invalid")
        content = record.get("content")
        if not isinstance(content, str) or not content.strip():
            reasons.append("content_missing")
        else:
            expected_hash = hashlib.sha256(
                content.encode("utf-8")
            ).hexdigest()
            supplied_hash = str(
                record.get("content_hash", "")
            ).lower()
            if supplied_hash != expected_hash:
                reasons.append("content_hash_mismatch")
        warnings = self._warnings(record.get("warnings", []))
        if any(
            "prompt_injection" in warning.lower()
            or "quarantin" in warning.lower()
            for warning in warnings
        ):
            reasons.append("unsafe_warning_present")
        return reasons

    def _verify_packet_integrity(
        self,
        *,
        packet: EvidenceReviewPacket,
        packet_path: Path,
    ) -> None:
        candidate_path = (
            self.project_root / packet.candidate_file
        ).resolve()
        self._validate_candidate_path(candidate_path)
        if self._file_hash(candidate_path) != packet.candidate_file_hash:
            raise RoutedEvidenceReviewError(
                "Candidate queue changed after packet generation"
            )
        payload = self.packet_payload(packet)
        supplied_hash = payload.pop("packet_hash")
        if self._payload_hash(payload) != supplied_hash:
            raise RoutedEvidenceReviewError(
                "Review packet hash verification failed"
            )
        registered = self.packet_registry.find(packet.packet_id)
        if registered is None:
            raise RoutedEvidenceReviewError(
                "Review packet is not registered"
            )
        if registered["packet_hash"] != packet.packet_hash:
            raise RoutedEvidenceReviewError(
                "Registered packet hash does not match"
            )
        if registered["packet_json_path"] != self._project_path(
            packet_path
        ):
            raise RoutedEvidenceReviewError(
                "Registered packet path does not match"
            )

    def _parse_decisions(
        self,
        *,
        packet: EvidenceReviewPacket,
        payload: dict[str, Any],
    ) -> tuple[str, list[ReviewDecisionInput]]:
        if str(payload.get("packet_id", "")) != packet.packet_id:
            raise RoutedEvidenceReviewError(
                "Decision file packet_id does not match"
            )
        if str(payload.get("packet_hash", "")) != packet.packet_hash:
            raise RoutedEvidenceReviewError(
                "Decision file packet_hash does not match"
            )
        reviewer_reference = self._reviewer_reference(
            payload.get("reviewer_reference", "")
        )
        raw_decisions = payload.get("decisions")
        if not isinstance(raw_decisions, list):
            raise RoutedEvidenceReviewError(
                "Decision file decisions must be a list"
            )

        eligible_ids = {
            item.review_id
            for item in packet.items
            if item.eligibility is ReviewEligibility.ELIGIBLE
        }
        seen: set[str] = set()
        decisions: list[ReviewDecisionInput] = []

        for raw in raw_decisions:
            if not isinstance(raw, dict):
                raise RoutedEvidenceReviewError(
                    "Every review decision must be an object"
                )
            review_id = self._required_text(
                "review_id",
                raw.get("review_id", ""),
            )
            if review_id in seen:
                raise RoutedEvidenceReviewError(
                    f"Duplicate decision for review_id: {review_id}"
                )
            seen.add(review_id)
            if review_id not in eligible_ids:
                raise RoutedEvidenceReviewError(
                    "Decision references a blocked or unknown candidate: "
                    f"{review_id}"
                )
            try:
                decision = HumanEvidenceDecision(
                    self._required_text(
                        "decision",
                        raw.get("decision", ""),
                    ).upper()
                )
            except ValueError as exc:
                raise RoutedEvidenceReviewError(
                    "Decision must be APPROVE, REJECT, or HOLD"
                ) from exc
            supports = raw.get("supports_validation")
            if supports is not None and not isinstance(supports, bool):
                raise RoutedEvidenceReviewError(
                    "supports_validation must be true, false, or null"
                )
            decisions.append(
                ReviewDecisionInput(
                    review_id=review_id,
                    decision=decision,
                    reason=self._required_text(
                        "reason",
                        raw.get("reason", ""),
                    ),
                    evidence_summary=str(
                        raw.get("evidence_summary", "")
                    ).strip(),
                    classification=str(
                        raw.get("classification", "")
                    ).strip().lower(),
                    signal_strength=str(
                        raw.get("signal_strength", "")
                    ).strip().lower(),
                    supports_validation=supports,
                )
            )

        missing = sorted(eligible_ids - seen)
        extra = sorted(seen - eligible_ids)
        if missing or extra:
            raise RoutedEvidenceReviewError(
                "Every eligible candidate requires exactly one decision. "
                f"Missing: {missing}. Extra: {extra}."
            )
        return reviewer_reference, decisions

    def _validate_decision_for_item(
        self,
        *,
        item: CandidateReviewItem,
        decision: ReviewDecisionInput,
    ) -> None:
        if item.eligibility is not ReviewEligibility.ELIGIBLE:
            raise RoutedEvidenceReviewError(
                "Blocked candidates cannot be resolved as human approvals"
            )
        if decision.decision is HumanEvidenceDecision.APPROVE:
            if not decision.evidence_summary:
                raise RoutedEvidenceReviewError(
                    "APPROVE requires evidence_summary"
                )
            if (
                decision.classification
                not in ALLOWED_APPROVAL_CLASSIFICATIONS
            ):
                raise RoutedEvidenceReviewError(
                    "APPROVE requires a valid non-rejected classification"
                )
            if (
                decision.signal_strength
                not in ALLOWED_SIGNAL_STRENGTHS
            ):
                raise RoutedEvidenceReviewError(
                    "APPROVE requires signal_strength"
                )
            if decision.supports_validation is None:
                raise RoutedEvidenceReviewError(
                    "APPROVE requires supports_validation"
                )
        elif decision.decision is HumanEvidenceDecision.REJECT:
            if decision.classification not in {"", "rejected"}:
                raise RoutedEvidenceReviewError(
                    "REJECT classification must be rejected or empty"
                )
        elif decision.classification == "rejected":
            raise RoutedEvidenceReviewError(
                "HOLD cannot use rejected classification"
            )

    @staticmethod
    def packet_payload(
        packet: EvidenceReviewPacket,
    ) -> dict[str, Any]:
        payload = asdict(packet)
        payload["items"] = [
            {
                **asdict(item),
                "eligibility": item.eligibility.value,
                "warnings": list(item.warnings),
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
    ) -> EvidenceReviewPacket:
        raw_items = payload.get("items")
        if not isinstance(raw_items, list):
            raise RoutedEvidenceReviewError(
                "Review packet items must be a list"
            )
        items: list[CandidateReviewItem] = []
        for raw in raw_items:
            if not isinstance(raw, dict):
                raise RoutedEvidenceReviewError(
                    "Review packet item must be an object"
                )
            try:
                eligibility = ReviewEligibility(
                    str(raw["eligibility"])
                )
            except (KeyError, ValueError) as exc:
                raise RoutedEvidenceReviewError(
                    "Review packet item has invalid eligibility"
                ) from exc
            items.append(
                CandidateReviewItem(
                    review_id=str(raw.get("review_id", "")),
                    candidate_index=int(
                        raw.get("candidate_index", 0)
                    ),
                    workflow_id=str(
                        raw.get("workflow_id", "")
                    ),
                    source_id=str(raw.get("source_id", "")),
                    adapter_name=str(
                        raw.get("adapter_name", "")
                    ),
                    adapter_version=str(
                        raw.get("adapter_version", "")
                    ),
                    requested_url=str(
                        raw.get("requested_url", "")
                    ),
                    final_url=str(raw.get("final_url", "")),
                    canonical_url=str(
                        raw.get("canonical_url", "")
                    ),
                    normalized_canonical_url=str(
                        raw.get(
                            "normalized_canonical_url",
                            "",
                        )
                    ),
                    title=str(raw.get("title", "")),
                    publisher_or_domain=str(
                        raw.get("publisher_or_domain", "")
                    ),
                    retrieved_at=str(
                        raw.get("retrieved_at", "")
                    ),
                    status=str(raw.get("status", "")),
                    content_ok=bool(
                        raw.get("content_ok", False)
                    ),
                    content_hash=str(
                        raw.get("content_hash", "")
                    ),
                    fetcher_used=str(
                        raw.get("fetcher_used", "")
                    ),
                    cached=bool(raw.get("cached", False)),
                    source_type_hint=str(
                        raw.get("source_type_hint", "")
                    ),
                    official_hint=bool(
                        raw.get("official_hint", False)
                    ),
                    published_date_hint=str(
                        raw.get("published_date_hint", "")
                    ),
                    warnings=tuple(
                        str(value)
                        for value in raw.get("warnings", [])
                    ),
                    eligibility=eligibility,
                    blocking_reasons=tuple(
                        str(value)
                        for value in raw.get(
                            "blocking_reasons",
                            [],
                        )
                    ),
                    duplicate_of_review_id=str(
                        raw.get(
                            "duplicate_of_review_id",
                            "",
                        )
                    ),
                )
            )
        try:
            return EvidenceReviewPacket(
                packet_id=str(payload["packet_id"]),
                workflow_id=str(payload["workflow_id"]),
                candidate_file=str(payload["candidate_file"]),
                candidate_file_hash=str(
                    payload["candidate_file_hash"]
                ),
                total_candidates=int(
                    payload["total_candidates"]
                ),
                eligible_candidates=int(
                    payload["eligible_candidates"]
                ),
                blocked_candidates=int(
                    payload["blocked_candidates"]
                ),
                duplicate_candidates=int(
                    payload["duplicate_candidates"]
                ),
                items=tuple(items),
                policy_version=str(payload["policy_version"]),
                created_at=str(payload["created_at"]),
                packet_hash=str(payload["packet_hash"]),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise RoutedEvidenceReviewError(
                "Review packet is missing required metadata"
            ) from exc

    @staticmethod
    def decision_template(
        packet: EvidenceReviewPacket,
    ) -> dict[str, Any]:
        return {
            "packet_id": packet.packet_id,
            "packet_hash": packet.packet_hash,
            "reviewer_reference": "",
            "instructions": (
                "Complete every eligible candidate. APPROVE requires "
                "evidence_summary, classification, signal_strength, and "
                "supports_validation. This file performs no action until "
                "passed to the Stage 4E resolution command."
            ),
            "allowed_decisions": [
                decision.value
                for decision in HumanEvidenceDecision
            ],
            "allowed_classifications": sorted(
                ALLOWED_CLASSIFICATIONS
            ),
            "allowed_signal_strengths": sorted(
                ALLOWED_SIGNAL_STRENGTHS
            ),
            "decisions": [
                {
                    "review_id": item.review_id,
                    "source_id": item.source_id,
                    "title": item.title,
                    "canonical_url": item.canonical_url,
                    "decision": "",
                    "reason": "",
                    "evidence_summary": "",
                    "classification": "",
                    "signal_strength": "",
                    "supports_validation": None,
                }
                for item in packet.items
                if item.eligibility is ReviewEligibility.ELIGIBLE
            ],
            "blocked_candidates": [
                {
                    "review_id": item.review_id,
                    "source_id": item.source_id,
                    "title": item.title,
                    "blocking_reasons": list(
                        item.blocking_reasons
                    ),
                    "duplicate_of_review_id": (
                        item.duplicate_of_review_id
                    ),
                }
                for item in packet.items
                if item.eligibility is ReviewEligibility.BLOCKED
            ],
        }

    @staticmethod
    def format_markdown(packet: EvidenceReviewPacket) -> str:
        lines = [
            f"# Routed Evidence Review Packet: {packet.workflow_id}",
            "",
            "## Packet metadata",
            "",
            f"- Packet ID: {packet.packet_id}",
            f"- Packet Hash: {packet.packet_hash}",
            f"- Policy Version: {packet.policy_version}",
            f"- Candidate File: {packet.candidate_file}",
            (
                "- Candidate File Hash: "
                f"{packet.candidate_file_hash}"
            ),
            f"- Total Candidates: {packet.total_candidates}",
            f"- Eligible: {packet.eligible_candidates}",
            f"- Blocked: {packet.blocked_candidates}",
            f"- Duplicates: {packet.duplicate_candidates}",
            f"- Created: {packet.created_at}",
            "",
            "## Governance boundary",
            "",
            (
                "This packet is read-only. It does not approve evidence, "
                "modify the validation evidence log, change theme state, "
                "publish content, or contact anyone."
            ),
            "",
            "## Candidates",
            "",
        ]
        for item in packet.items:
            lines.extend(
                [
                    (
                        f"### {item.source_id or 'Unidentified'} — "
                        f"{item.eligibility.value}"
                    ),
                    "",
                    f"- Review ID: {item.review_id}",
                    f"- Title: {item.title or 'Missing'}",
                    f"- Adapter: {item.adapter_name} {item.adapter_version}",
                    f"- Canonical URL: {item.canonical_url}",
                    f"- Retrieved: {item.retrieved_at}",
                    f"- Fetcher: {item.fetcher_used}",
                    f"- Cached: {item.cached}",
                    f"- Content Hash: {item.content_hash}",
                    (
                        "- Source Type Hint: "
                        f"{item.source_type_hint or 'None'}"
                    ),
                    f"- Official Hint: {item.official_hint}",
                    (
                        "- Warnings: "
                        f"{', '.join(item.warnings) or 'None'}"
                    ),
                    (
                        "- Blocking Reasons: "
                        f"{', '.join(item.blocking_reasons) or 'None'}"
                    ),
                    (
                        "- Duplicate Of: "
                        f"{item.duplicate_of_review_id or 'None'}"
                    ),
                    "",
                ]
            )
        return "\n".join(lines)

    @staticmethod
    def _item_payload(
        item: CandidateReviewItem,
    ) -> dict[str, Any]:
        payload = asdict(item)
        payload["eligibility"] = item.eligibility.value
        payload["warnings"] = list(item.warnings)
        payload["blocking_reasons"] = list(
            item.blocking_reasons
        )
        return payload

    def _validate_candidate_path(self, path: Path) -> Path:
        resolved = path.resolve()
        if not self._is_within(resolved, self.candidate_root):
            raise RoutedEvidenceReviewError(
                "Candidate file must stay inside "
                "data/research/evidence_candidates"
            )
        if resolved.suffix != ".jsonl":
            raise RoutedEvidenceReviewError(
                "Candidate file must be JSONL"
            )
        if not resolved.is_file():
            raise RoutedEvidenceReviewError(
                f"Candidate file does not exist: {path}"
            )
        return resolved

    def _validate_report_path(
        self,
        path: Path,
        *,
        root: Path,
        suffix: str,
        label: str,
        must_exist: bool = False,
    ) -> Path:
        resolved = path.resolve()
        if not self._is_within(resolved, root):
            raise RoutedEvidenceReviewError(
                f"{label} must stay inside "
                f"{self._project_path(root)}"
            )
        if resolved.suffix != suffix:
            raise RoutedEvidenceReviewError(
                f"{label} must use {suffix}"
            )
        if must_exist and not resolved.is_file():
            raise RoutedEvidenceReviewError(
                f"{label} does not exist"
            )
        return resolved

    @staticmethod
    def _load_candidate_records(
        path: Path,
    ) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []
        try:
            lines = path.read_text(
                encoding="utf-8"
            ).splitlines()
        except OSError as exc:
            raise RoutedEvidenceReviewError(
                "Candidate file could not be read"
            ) from exc
        for line_number, line in enumerate(lines, start=1):
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                raise RoutedEvidenceReviewError(
                    "Candidate JSONL contains invalid JSON at "
                    f"line {line_number}"
                ) from exc
            if not isinstance(record, dict):
                raise RoutedEvidenceReviewError(
                    "Every candidate JSONL line must be an object"
                )
            records.append(record)
        if not records:
            raise RoutedEvidenceReviewError(
                "Candidate file contains no records"
            )
        return records

    @staticmethod
    def _load_json_object(path: Path) -> dict[str, Any]:
        try:
            payload = json.loads(
                path.read_text(encoding="utf-8")
            )
        except (OSError, json.JSONDecodeError) as exc:
            raise RoutedEvidenceReviewError(
                f"Could not read JSON object: {path}"
            ) from exc
        if not isinstance(payload, dict):
            raise RoutedEvidenceReviewError(
                "JSON file must contain an object"
            )
        return payload

    def _project_path(self, path: Path) -> str:
        try:
            return str(path.resolve().relative_to(self.project_root))
        except ValueError as exc:
            raise RoutedEvidenceReviewError(
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
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    @staticmethod
    def _review_id(
        *,
        workflow_id: str,
        source_id: str,
        normalized_url: str,
        content_hash: str,
    ) -> str:
        material = (
            f"{workflow_id}|{source_id}|"
            f"{normalized_url}|{content_hash}"
        ).encode()
        return "ER-" + hashlib.sha256(material).hexdigest()[:20]

    @staticmethod
    def _normalize_url(value: str) -> str:
        try:
            parsed = urlsplit(value.strip())
        except ValueError:
            return ""
        host = (parsed.hostname or "").lower().rstrip(".")
        if parsed.scheme not in {"http", "https"} or not host:
            return ""
        port = ""
        try:
            if parsed.port is not None:
                port = f":{parsed.port}"
        except ValueError:
            return ""
        path = parsed.path.rstrip("/") or "/"
        return f"{parsed.scheme.lower()}://{host}{port}{path}"

    @staticmethod
    def _valid_public_url(value: str) -> bool:
        try:
            parsed = urlsplit(value.strip())
        except ValueError:
            return False
        return (
            parsed.scheme in {"http", "https"}
            and bool(parsed.hostname)
            and parsed.username is None
            and parsed.password is None
        )

    @staticmethod
    def _warnings(value: Any) -> tuple[str, ...]:
        if value is None:
            return ()
        if isinstance(value, str):
            return (value,) if value.strip() else ()
        if isinstance(value, list):
            return tuple(
                str(item)
                for item in value
                if str(item).strip()
            )
        return (str(value),)

    @staticmethod
    def _required_text(
        field_name: str,
        value: Any,
    ) -> str:
        if not isinstance(value, str) or not value.strip():
            raise RoutedEvidenceReviewError(
                f"{field_name} is required"
            )
        return " ".join(value.split())

    @classmethod
    def _reviewer_reference(cls, value: Any) -> str:
        reference = cls._required_text(
            "reviewer_reference",
            value,
        )
        if len(reference) > 120:
            raise RoutedEvidenceReviewError(
                "reviewer_reference must be 120 characters or fewer"
            )
        if not all(
            character.isalnum()
            or character in {"_", "-", "."}
            for character in reference
        ):
            raise RoutedEvidenceReviewError(
                "reviewer_reference may use only letters, numbers, "
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
            raise RoutedEvidenceReviewError(
                "Invalid workflow identifier"
            )
        return safe[:100]

    @staticmethod
    def _is_within(path: Path, root: Path) -> bool:
        try:
            path.relative_to(root)
            return True
        except ValueError:
            return False
