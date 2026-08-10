"""Convert a supplied public Reddit post into an evidence candidate.

This adapter does not fetch Reddit. It reuses the existing local RedditAdapter
for pipeline processing and only accepts post content supplied by a human or an
approved upstream source.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime
from urllib.parse import urlsplit

from src.adapters.reddit_adapter import RedditAdapter, RedditPost
from src.adapters.research_adapter import CandidateStatus, EvidenceCandidate


class RedditLocalEvidenceAdapterError(ValueError):
    """Raised when supplied Reddit evidence violates the local intake boundary."""


@dataclass(frozen=True)
class RedditLocalEvidenceResult:
    candidate: EvidenceCandidate | None
    processed_count: int
    accepted_count: int
    rejected_count: int
    report_paths: tuple[str, ...]
    reason: str


class RedditLocalEvidenceAdapter:
    """Wrap the existing RedditAdapter without adding live network access."""

    ADAPTER_NAME = "reddit-local"
    ADAPTER_VERSION = "1.0"
    MAX_CONTENT_CHARS = 40_000
    REDDIT_HOSTS = frozenset(
        {
            "reddit.com",
            "www.reddit.com",
            "old.reddit.com",
            "redd.it",
            "www.redd.it",
        }
    )

    def __init__(self, adapter: RedditAdapter | None = None) -> None:
        self.adapter = adapter or RedditAdapter()

    def process_post(
        self,
        *,
        workflow_id: str,
        requested_url: str,
        post: RedditPost,
        industry: str,
    ) -> RedditLocalEvidenceResult:
        self._validate_inputs(
            workflow_id=workflow_id,
            requested_url=requested_url,
            post=post,
            industry=industry,
        )
        result = self.adapter.process_posts(
            posts=[post],
            industry=industry.strip(),
        )
        report_paths = tuple(
            str(item.report_path)
            for item in result.results
        )
        if result.accepted_count != 1:
            return RedditLocalEvidenceResult(
                candidate=None,
                processed_count=result.processed_count,
                accepted_count=result.accepted_count,
                rejected_count=result.rejected_count,
                report_paths=report_paths,
                reason="reddit_post_rejected_by_existing_pipeline",
            )

        content = post.full_text[: self.MAX_CONTENT_CHARS]
        content_hash = hashlib.sha256(
            content.encode("utf-8")
        ).hexdigest()
        final_url = (post.url or requested_url).strip()
        hostname = (urlsplit(final_url).hostname or "").lower()

        candidate = EvidenceCandidate(
            workflow_id=workflow_id,
            adapter_name=self.ADAPTER_NAME,
            adapter_version=self.ADAPTER_VERSION,
            requested_url=requested_url,
            final_url=final_url,
            canonical_url=final_url,
            title=post.title.strip(),
            publisher_or_domain=hostname or "reddit.com",
            retrieved_at=datetime.now(UTC).isoformat(),
            status=CandidateStatus.CANDIDATE,
            content_ok=True,
            content=content,
            content_hash=content_hash,
            fetcher_used="supplied_public_post",
            cached=False,
            warnings=(
                "content_supplied_to_local_adapter_not_live_fetched",
            ),
            source_type_hint="reddit",
            official_hint=False,
            published_date_hint="",
            raw_metadata={
                "subreddit": post.subreddit,
                "report_paths": list(report_paths),
                "network_fetch_performed": False,
            },
        )
        return RedditLocalEvidenceResult(
            candidate=candidate,
            processed_count=result.processed_count,
            accepted_count=result.accepted_count,
            rejected_count=result.rejected_count,
            report_paths=report_paths,
            reason="reddit_post_accepted_by_existing_pipeline",
        )

    def _validate_inputs(
        self,
        *,
        workflow_id: str,
        requested_url: str,
        post: RedditPost,
        industry: str,
    ) -> None:
        if not workflow_id.strip():
            raise RedditLocalEvidenceAdapterError(
                "workflow_id cannot be empty"
            )
        if not industry.strip():
            raise RedditLocalEvidenceAdapterError(
                "industry cannot be empty"
            )
        if not post.subreddit.strip():
            raise RedditLocalEvidenceAdapterError(
                "subreddit cannot be empty"
            )
        if not post.full_text.strip():
            raise RedditLocalEvidenceAdapterError(
                "Reddit post content cannot be empty"
            )
        if len(post.full_text) > self.MAX_CONTENT_CHARS:
            raise RedditLocalEvidenceAdapterError(
                "Reddit post exceeds the local evidence content limit"
            )
        for label, url in (
            ("requested_url", requested_url),
            ("post.url", post.url or requested_url),
        ):
            hostname = (urlsplit(url).hostname or "").lower().rstrip(".")
            if hostname not in self.REDDIT_HOSTS:
                raise RedditLocalEvidenceAdapterError(
                    f"{label} is not a supported public Reddit URL"
                )
