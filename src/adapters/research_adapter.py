"""Provider-neutral research adapter contracts.

The factory owns these models. External research tools may produce candidates,
but they cannot declare claims true or write to the approved evidence registry.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Protocol


class CandidateStatus(str, Enum):
    CANDIDATE = "candidate"
    QUARANTINED = "quarantined"
    BLOCKED = "blocked"
    FAILED = "failed"


@dataclass(frozen=True)
class SearchRequest:
    workflow_id: str
    query: str
    allowed_domains: tuple[str, ...]
    max_results: int = 10
    freshness: str | None = None


@dataclass(frozen=True)
class SearchResult:
    title: str
    url: str
    snippet: str = ""
    domain: str = ""
    rank: int = 0
    relevance_score: float | None = None
    allowed_to_fetch: bool = False
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class FetchRequest:
    workflow_id: str
    url: str
    focus: str | None = None
    max_content_chars: int = 40_000


@dataclass(frozen=True)
class EvidenceCandidate:
    workflow_id: str
    adapter_name: str
    adapter_version: str
    requested_url: str
    final_url: str
    canonical_url: str
    title: str
    publisher_or_domain: str
    retrieved_at: str
    status: CandidateStatus
    content_ok: bool
    content: str
    content_hash: str
    fetcher_used: str
    cached: bool
    warnings: tuple[str, ...] = ()
    source_type_hint: str = ""
    official_hint: bool = False
    published_date_hint: str = ""
    raw_metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AdapterHealth:
    healthy: bool
    adapter_name: str
    adapter_version: str
    details: dict[str, Any] = field(default_factory=dict)


class ResearchAdapter(Protocol):
    def search(self, request: SearchRequest) -> list[SearchResult]:
        """Return discovery candidates. No source is approved at this stage."""

    def fetch(self, request: FetchRequest) -> EvidenceCandidate:
        """Return one untrusted evidence candidate."""

    def health(self) -> AdapterHealth:
        """Return adapter health without taking protected action."""
