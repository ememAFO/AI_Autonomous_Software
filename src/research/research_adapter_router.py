"""Stage 4D routing for governed research source intake."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from urllib.parse import urlsplit

from src.adapters.hound_adapter import (
    HoundAdapterError,
    HoundResearchAdapter,
)
from src.adapters.hound_policy import HoundPolicyError
from src.adapters.hound_transport import HoundTransportError
from src.adapters.reddit_adapter import RedditPost
from src.adapters.reddit_local_evidence_adapter import (
    RedditLocalEvidenceAdapter,
    RedditLocalEvidenceAdapterError,
)
from src.adapters.research_adapter import CandidateStatus, FetchRequest
from src.research.research_routing_review_queue import (
    ResearchRoutingReviewQueue,
    RoutingReviewRecord,
)
from src.research.routed_evidence_candidate_queue import (
    RoutedEvidenceCandidateQueue,
)

AuditSink = Callable[[dict[str, object]], None]


class RouteTarget(StrEnum):
    HOUND = "hound"
    REDDIT_LOCAL = "reddit_local"
    HUMAN_REVIEW = "human_review"
    BLOCKED = "blocked"


class RouteStatus(StrEnum):
    QUEUED = "queued"
    QUARANTINED = "quarantined"
    REVIEW_REQUIRED = "review_required"
    BLOCKED = "blocked"


@dataclass(frozen=True)
class RoutedSourceRequest:
    workflow_id: str
    source_id: str
    url: str
    focus: str = ""
    industry: str = ""
    reddit_post: RedditPost | None = None


@dataclass(frozen=True)
class ResearchRouteResult:
    workflow_id: str
    source_id: str
    url: str
    target: RouteTarget
    status: RouteStatus
    reason: str
    candidate_queue_path: str = ""
    review_queue_path: str = ""
    candidate_status: str = ""


class ResearchAdapterRouter:
    """Route each source to one governed adapter or human review."""

    REDDIT_HOSTS = frozenset(
        {
            "reddit.com",
            "www.reddit.com",
            "old.reddit.com",
            "redd.it",
            "www.redd.it",
        }
    )
    EXPECTED_HOUND_ERRORS = (
        HoundAdapterError,
        HoundPolicyError,
        HoundTransportError,
        OSError,
        RuntimeError,
        TypeError,
        ValueError,
    )

    def __init__(
        self,
        *,
        hound_adapter: HoundResearchAdapter,
        reddit_adapter: RedditLocalEvidenceAdapter | None = None,
        candidate_queue: RoutedEvidenceCandidateQueue | None = None,
        review_queue: ResearchRoutingReviewQueue | None = None,
        audit_sink: AuditSink | None = None,
    ) -> None:
        self.hound_adapter = hound_adapter
        self.reddit_adapter = (
            reddit_adapter or RedditLocalEvidenceAdapter()
        )
        self.candidate_queue = (
            candidate_queue or RoutedEvidenceCandidateQueue()
        )
        self.review_queue = (
            review_queue or ResearchRoutingReviewQueue()
        )
        self.audit_sink = audit_sink or (lambda event: None)

    def route(self, request: RoutedSourceRequest) -> ResearchRouteResult:
        validation_error = self._validate_request(request)
        if validation_error:
            return self._record_review(
                request=request,
                target=RouteTarget.BLOCKED,
                status=RouteStatus.BLOCKED,
                reason=validation_error,
            )

        hostname = (urlsplit(request.url).hostname or "").lower()
        if hostname in self.REDDIT_HOSTS:
            return self._route_reddit(request)
        return self._route_hound(request)

    def _route_hound(
        self,
        request: RoutedSourceRequest,
    ) -> ResearchRouteResult:
        try:
            candidate = self.hound_adapter.fetch(
                FetchRequest(
                    workflow_id=request.workflow_id,
                    url=request.url,
                    focus=request.focus or None,
                )
            )
        except self.EXPECTED_HOUND_ERRORS as exc:
            return self._record_review(
                request=request,
                target=RouteTarget.HUMAN_REVIEW,
                status=RouteStatus.REVIEW_REQUIRED,
                reason="hound_fetch_failed_or_blocked",
                error=f"{type(exc).__name__}: {exc}",
            )

        candidate_path = self.candidate_queue.append(
            source_id=request.source_id,
            candidate=candidate,
        )
        if candidate.status is CandidateStatus.CANDIDATE:
            result = ResearchRouteResult(
                workflow_id=request.workflow_id,
                source_id=request.source_id,
                url=request.url,
                target=RouteTarget.HOUND,
                status=RouteStatus.QUEUED,
                reason="hound_candidate_queued",
                candidate_queue_path=str(candidate_path),
                candidate_status=candidate.status.value,
            )
            self._audit(result)
            return result

        review_path = self.review_queue.append(
            RoutingReviewRecord(
                workflow_id=request.workflow_id,
                source_id=request.source_id,
                url=request.url,
                route_target=RouteTarget.HOUND.value,
                reason="hound_candidate_requires_human_review",
                details={
                    "candidate_status": candidate.status.value,
                    "warnings": list(candidate.warnings),
                    "candidate_queue_path": str(candidate_path),
                },
            )
        )
        status = (
            RouteStatus.QUARANTINED
            if candidate.status is CandidateStatus.QUARANTINED
            else RouteStatus.REVIEW_REQUIRED
        )
        result = ResearchRouteResult(
            workflow_id=request.workflow_id,
            source_id=request.source_id,
            url=request.url,
            target=RouteTarget.HOUND,
            status=status,
            reason="hound_candidate_requires_human_review",
            candidate_queue_path=str(candidate_path),
            review_queue_path=str(review_path),
            candidate_status=candidate.status.value,
        )
        self._audit(result)
        return result

    def _route_reddit(
        self,
        request: RoutedSourceRequest,
    ) -> ResearchRouteResult:
        if request.reddit_post is None:
            return self._record_review(
                request=request,
                target=RouteTarget.HUMAN_REVIEW,
                status=RouteStatus.REVIEW_REQUIRED,
                reason="live_reddit_url_fetch_not_supported",
                details={
                    "boundary": (
                        "Supply public post content through an approved "
                        "source or resolve manually. No browser fallback."
                    )
                },
            )

        try:
            reddit_result = self.reddit_adapter.process_post(
                workflow_id=request.workflow_id,
                requested_url=request.url,
                post=request.reddit_post,
                industry=request.industry,
            )
        except RedditLocalEvidenceAdapterError as exc:
            return self._record_review(
                request=request,
                target=RouteTarget.HUMAN_REVIEW,
                status=RouteStatus.REVIEW_REQUIRED,
                reason="reddit_local_intake_blocked",
                error=f"{type(exc).__name__}: {exc}",
            )

        if reddit_result.candidate is None:
            return self._record_review(
                request=request,
                target=RouteTarget.HUMAN_REVIEW,
                status=RouteStatus.REVIEW_REQUIRED,
                reason=reddit_result.reason,
                details={
                    "processed_count": reddit_result.processed_count,
                    "accepted_count": reddit_result.accepted_count,
                    "rejected_count": reddit_result.rejected_count,
                    "report_paths": list(reddit_result.report_paths),
                },
            )

        candidate_path = self.candidate_queue.append(
            source_id=request.source_id,
            candidate=reddit_result.candidate,
        )
        result = ResearchRouteResult(
            workflow_id=request.workflow_id,
            source_id=request.source_id,
            url=request.url,
            target=RouteTarget.REDDIT_LOCAL,
            status=RouteStatus.QUEUED,
            reason=reddit_result.reason,
            candidate_queue_path=str(candidate_path),
            candidate_status=reddit_result.candidate.status.value,
        )
        self._audit(result)
        return result

    def _record_review(
        self,
        *,
        request: RoutedSourceRequest,
        target: RouteTarget,
        status: RouteStatus,
        reason: str,
        error: str = "",
        details: dict[str, object] | None = None,
    ) -> ResearchRouteResult:
        review_path = self.review_queue.append(
            RoutingReviewRecord(
                workflow_id=request.workflow_id,
                source_id=request.source_id,
                url=request.url,
                route_target=target.value,
                reason=reason,
                error=error,
                details=details or {},
            )
        )
        result = ResearchRouteResult(
            workflow_id=request.workflow_id,
            source_id=request.source_id,
            url=request.url,
            target=target,
            status=status,
            reason=reason,
            review_queue_path=str(review_path),
        )
        self._audit(result)
        return result

    @staticmethod
    def _validate_request(
        request: RoutedSourceRequest,
    ) -> str:
        if not request.workflow_id.strip():
            return "workflow_id_cannot_be_empty"
        if not request.source_id.strip():
            return "source_id_cannot_be_empty"
        try:
            parsed = urlsplit(request.url.strip())
        except ValueError:
            return "invalid_url"
        if parsed.scheme not in {"http", "https"}:
            return "unsupported_url_scheme"
        if not parsed.hostname:
            return "missing_url_hostname"
        if parsed.username or parsed.password:
            return "url_userinfo_not_allowed"
        return ""

    def _audit(self, result: ResearchRouteResult) -> None:
        self.audit_sink(
            {
                "action": "research_source_routed",
                "status": result.status.value,
                "details": {
                    "workflow_id": result.workflow_id,
                    "source_id": result.source_id,
                    "url": result.url,
                    "target": result.target.value,
                    "reason": result.reason,
                    "candidate_queue_path": (
                        result.candidate_queue_path
                    ),
                    "review_queue_path": result.review_queue_path,
                    "candidate_status": result.candidate_status,
                },
            }
        )
