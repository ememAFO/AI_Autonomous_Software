"""Governed Hound adapter for Stage 4C.

The adapter exposes only search and HTTP-only fetch. It blocks browser actions,
proxies, cookies, authentication, crawling, cached current-state retrieval and
direct approved-registry writes.
"""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any, ClassVar
from urllib.parse import urlsplit

from src.adapters.hound_policy import HoundPilotPolicy, HoundPolicyError
from src.adapters.hound_robots import (
    FailClosedRobotsChecker,
    RobotsDocument,
    RobotsStatus,
)
from src.adapters.hound_transport import ToolTransport
from src.adapters.research_adapter import (
    AdapterHealth,
    CandidateStatus,
    EvidenceCandidate,
    FetchRequest,
    SearchRequest,
    SearchResult,
)

AuditSink = Callable[[dict[str, Any]], None]


class HoundAdapterError(RuntimeError):
    """Raised when Hound is incompatible with the governed adapter."""


class HoundResearchAdapter:
    ADAPTER_NAME = "hound"
    TOOL_ALIASES: ClassVar[dict[str, tuple[str, str]]] = {
        "smart_search": ("smart_search", "mcp_smart_search"),
        "smart_fetch": ("smart_fetch", "mcp_smart_fetch"),
        "version": ("version", "mcp_version"),
    }

    def __init__(
        self,
        transport: ToolTransport,
        policy: HoundPilotPolicy,
        *,
        robots_checker: FailClosedRobotsChecker | None = None,
        audit_sink: AuditSink | None = None,
    ) -> None:
        self.transport = transport
        self.policy = policy
        self.robots_checker = robots_checker or FailClosedRobotsChecker()
        self.audit_sink = audit_sink or (lambda event: None)
        self._fetch_count: defaultdict[str, int] = defaultdict(int)
        self._tool_names: dict[str, str] = {}
        self._version = self._load_and_validate_tools()

    def health(self) -> AdapterHealth:
        details = self.transport.health()
        healthy = bool(details.get("running", True))
        return AdapterHealth(
            healthy=healthy,
            adapter_name=self.ADAPTER_NAME,
            adapter_version=self._version,
            details=details,
        )

    def search(self, request: SearchRequest) -> list[SearchResult]:
        self.policy.validate_search_request(
            workflow_id=request.workflow_id,
            query=request.query,
            allowed_domains=request.allowed_domains,
            max_results=request.max_results,
        )

        results: list[SearchResult] = []
        seen: set[str] = set()

        # Hound supports one site filter per call, so multiple permitted domains
        # are searched separately and merged deterministically.
        for domain in request.allowed_domains:
            arguments = self._build_search_arguments(
                query=request.query,
                site=domain,
                max_results=request.max_results,
                freshness=request.freshness,
            )
            self._audit(
                "hound_search_requested",
                request.workflow_id,
                {
                    "query": request.query,
                    "domain": domain,
                    "arguments": arguments,
                },
            )
            raw = self.transport.call_tool(
                self._tool_names["smart_search"],
                arguments,
            )
            for item in self._extract_search_items(raw):
                url = str(item.get("url", "")).strip()
                if not url or url in seen:
                    continue
                seen.add(url)

                decision = self.policy.check_url(url)
                in_query_scope = self._hostname_matches_any_domain(
                    decision.hostname,
                    request.allowed_domains,
                )
                allowed = decision.allowed and in_query_scope

                if not decision.allowed:
                    warnings = (decision.reason,)
                elif not in_query_scope:
                    warnings = ("search_result_outside_declared_domains",)
                else:
                    warnings = ()

                title = str(item.get("title", "")).strip()
                snippet = str(
                    item.get("snippet", item.get("description", ""))
                ).strip()
                relevance = self._optional_float(item.get("relevance_score"))
                results.append(
                    SearchResult(
                        title=title,
                        url=url,
                        snippet=snippet,
                        domain=decision.hostname,
                        rank=len(results) + 1,
                        relevance_score=relevance,
                        allowed_to_fetch=allowed,
                        warnings=warnings,
                    )
                )

        results.sort(
            key=lambda item: (
                item.relevance_score is None,
                -(item.relevance_score or 0.0),
                item.rank,
                item.url,
            )
        )
        return [
            SearchResult(
                title=item.title,
                url=item.url,
                snippet=item.snippet,
                domain=item.domain,
                rank=index,
                relevance_score=item.relevance_score,
                allowed_to_fetch=item.allowed_to_fetch,
                warnings=item.warnings,
            )
            for index, item in enumerate(
                results[: request.max_results],
                start=1,
            )
        ]

    def fetch(self, request: FetchRequest) -> EvidenceCandidate:
        if not request.workflow_id.strip():
            raise HoundPolicyError("workflow_id cannot be empty")
        if request.max_content_chars > self.policy.max_content_chars:
            raise HoundPolicyError(
                "Requested content limit exceeds pilot policy"
            )

        decision = self.policy.check_url(request.url)
        if not decision.allowed:
            self._audit(
                "hound_fetch_blocked",
                request.workflow_id,
                {"url": request.url, "reason": decision.reason},
            )
            raise HoundPolicyError(
                f"Fetch blocked for {request.url}: {decision.reason}"
            )

        self._fetch_count[request.workflow_id] += 1
        if (
            self._fetch_count[request.workflow_id]
            > self.policy.max_fetches_per_workflow
        ):
            raise HoundPolicyError("Workflow fetch budget exceeded")

        robots_url = self.robots_checker.robots_url_for(request.url)
        robots_raw = self.transport.call_tool(
            self._tool_names["smart_fetch"],
            self._build_fetch_arguments(
                robots_url,
                focus=None,
                respect_robots=False,
                max_content_chars=20_000,
            ),
        )
        robots_doc = self._robots_document(robots_raw)
        robots_decision = self.robots_checker.decide(
            request.url,
            robots_doc,
        )
        self._audit(
            "hound_robots_decision",
            request.workflow_id,
            {
                "url": request.url,
                "robots_url": robots_url,
                "status": robots_decision.status.value,
                "reason": robots_decision.reason,
            },
        )
        if robots_decision.status is not RobotsStatus.ALLOWED:
            raise HoundPolicyError(
                "Fetch blocked by robots policy: "
                f"{robots_decision.status.value}:"
                f"{robots_decision.reason}"
            )

        raw = self.transport.call_tool(
            self._tool_names["smart_fetch"],
            self._build_fetch_arguments(
                request.url,
                focus=request.focus,
                respect_robots=True,
                max_content_chars=request.max_content_chars,
            ),
        )
        candidate = self._candidate_from_raw(request, raw)

        # Postconditions prevent a provider defect from silently relaxing the
        # HTTP-only and fresh-retrieval policy.
        if candidate.fetcher_used not in {"http", "none"}:
            self._audit(
                "hound_browser_activation_blocked",
                request.workflow_id,
                {
                    "url": request.url,
                    "fetcher_used": candidate.fetcher_used,
                },
            )
            raise HoundPolicyError(
                "Hound returned a prohibited fetcher: "
                f"{candidate.fetcher_used}"
            )
        if candidate.cached:
            raise HoundPolicyError(
                "Hound returned cached content despite cache_ttl=0"
            )

        final_decision = self.policy.check_url(candidate.final_url)
        if not final_decision.allowed:
            self._audit(
                "hound_redirect_blocked",
                request.workflow_id,
                {
                    "requested_url": request.url,
                    "final_url": candidate.final_url,
                    "reason": final_decision.reason,
                },
            )
            raise HoundPolicyError(
                "Final URL blocked after redirect: "
                f"{final_decision.reason}"
            )

        injection_findings = self.policy.scan_untrusted_content(
            candidate.content
        )
        if injection_findings:
            candidate = EvidenceCandidate(
                **{
                    **candidate.__dict__,
                    "status": CandidateStatus.QUARANTINED,
                    "warnings": tuple(candidate.warnings)
                    + injection_findings,
                }
            )

        self._audit(
            "hound_candidate_created",
            request.workflow_id,
            {
                "requested_url": candidate.requested_url,
                "final_url": candidate.final_url,
                "status": candidate.status.value,
                "content_ok": candidate.content_ok,
                "warnings": list(candidate.warnings),
            },
        )
        return candidate

    def _load_and_validate_tools(self) -> str:
        health = self.transport.health()
        available_tools = {
            str(name)
            for name in health.get("tools", [])
        }

        for logical_name, aliases in self.TOOL_ALIASES.items():
            actual_name = next(
                (
                    alias
                    for alias in aliases
                    if alias in available_tools
                ),
                None,
            )
            if actual_name is None:
                raise HoundAdapterError(
                    "Required Hound tool not available: "
                    f"{logical_name}. Advertised tools: "
                    f"{sorted(available_tools)}"
                )
            self.transport.tool_schema(actual_name)
            self._tool_names[logical_name] = actual_name

        raw_version = self.transport.call_tool(
            self._tool_names["version"],
            {},
        )
        if isinstance(raw_version, dict):
            version = str(
                raw_version.get(
                    "version",
                    raw_version.get("installed_version", "unknown"),
                )
            )
        else:
            version = str(raw_version)
        return version or "unknown"

    def _build_search_arguments(
        self,
        *,
        query: str,
        site: str,
        max_results: int,
        freshness: str | None,
    ) -> dict[str, Any]:
        schema = self.transport.tool_schema(
            self._tool_names["smart_search"]
        )
        properties = schema.get("properties", {})
        args: dict[str, Any] = {"query": query}

        # Hound 13.x exposes filters only through an `options` object.
        if "options" in properties:
            options: dict[str, Any] = {
                "site": site,
                "max_results": max_results,
                "cache_ttl": 0,
                "mode": "auto",
            }
            if freshness:
                options["freshness"] = freshness
            args["options"] = options
            return args

        # Compatibility path for providers exposing expanded top-level fields.
        if "site" in properties:
            args["site"] = site
        for count_name in ("max_results", "num_results", "limit"):
            if count_name in properties:
                args[count_name] = max_results
                break
        if "cache_ttl" in properties:
            args["cache_ttl"] = 0
        if freshness and "freshness" in properties:
            args["freshness"] = freshness
        return args

    def _build_fetch_arguments(
        self,
        url: str,
        *,
        focus: str | None,
        respect_robots: bool,
        max_content_chars: int,
    ) -> dict[str, Any]:
        schema = self.transport.tool_schema(
            self._tool_names["smart_fetch"]
        )
        properties = schema.get("properties", {})
        args: dict[str, Any] = {"url": url}
        options: dict[str, Any] = {}

        # Explicitly pin Hound to HTTP. Omitting this permits auto-escalation.
        if "force_fetcher" in properties:
            args["force_fetcher"] = "http"
        elif "options" in properties:
            options["force_fetcher"] = "http"
        else:
            raise HoundAdapterError(
                "Installed Hound does not expose force_fetcher; "
                "HTTP-only policy cannot be enforced"
            )

        top_level_values = {
            "cache_ttl": 0,
            "max_content_chars": max_content_chars,
            "extraction_type": "markdown",
        }
        if focus:
            top_level_values["focus"] = focus
        for name, value in top_level_values.items():
            if name in properties:
                args[name] = value
            elif "options" in properties:
                options[name] = value

        if "options" in properties:
            options.update(
                {
                    "respect_robots": respect_robots,
                    "solve_cloudflare": False,
                    "include_links": False,
                }
            )
            args["options"] = options
        elif "respect_robots" in properties:
            args["respect_robots"] = respect_robots

        prohibited = {
            "actions",
            "cookies",
            "extra_headers",
            "headers",
            "proxy",
            "capture_xhr",
            "fold_captured",
            "password",
        }
        if prohibited.intersection(args):
            raise HoundAdapterError(
                "Prohibited Hound argument was constructed"
            )
        if prohibited.intersection(options):
            raise HoundAdapterError(
                "Prohibited Hound option was constructed"
            )
        return args

    @staticmethod
    def _extract_search_items(raw: Any) -> list[dict[str, Any]]:
        if isinstance(raw, list):
            return [item for item in raw if isinstance(item, dict)]
        if not isinstance(raw, dict):
            return []
        for key in ("results", "items", "data"):
            value = raw.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
        return []

    def _candidate_from_raw(
        self,
        request: FetchRequest,
        raw: Any,
    ) -> EvidenceCandidate:
        if not isinstance(raw, dict):
            raise HoundAdapterError(
                "Hound fetch returned a non-object response"
            )

        content = self._normalize_content(
            raw.get(
                "content",
                raw.get("markdown", raw.get("text", "")),
            )
        )
        metadata = raw.get("metadata", {})
        if not isinstance(metadata, dict):
            metadata = {}

        requested_url = request.url
        final_url = str(
            raw.get(
                "final_url",
                raw.get("url", requested_url),
            )
        ).strip() or requested_url
        canonical = str(
            raw.get(
                "canonical_url",
                metadata.get(
                    "canonical",
                    metadata.get("canonical_url", final_url),
                ),
            )
        ).strip() or final_url
        title = str(
            raw.get("title", metadata.get("title", ""))
        ).strip()
        domain = (urlsplit(final_url).hostname or "").lower()
        content_ok = bool(raw.get("content_ok", bool(content.strip())))
        warnings = self._normalize_warnings(
            raw.get("warnings", raw.get("warning", []))
        )
        status = (
            CandidateStatus.CANDIDATE
            if content_ok
            else CandidateStatus.FAILED
        )

        content = content[: request.max_content_chars]
        digest = hashlib.sha256(
            content.encode("utf-8")
        ).hexdigest()
        retrieved_at = str(
            raw.get(
                "fetched_at",
                datetime.now(timezone.utc).isoformat(),
            )
        )
        return EvidenceCandidate(
            workflow_id=request.workflow_id,
            adapter_name=self.ADAPTER_NAME,
            adapter_version=self._version,
            requested_url=requested_url,
            final_url=final_url,
            canonical_url=canonical,
            title=title,
            publisher_or_domain=str(
                raw.get(
                    "site_name",
                    metadata.get("site_name", domain),
                )
            ),
            retrieved_at=retrieved_at,
            status=status,
            content_ok=content_ok,
            content=content,
            content_hash=digest,
            fetcher_used=str(raw.get("fetcher_used", "none")),
            cached=bool(raw.get("cached", False)),
            warnings=warnings,
            source_type_hint=str(raw.get("source_type", "")),
            official_hint=bool(raw.get("is_official", False)),
            published_date_hint=str(
                raw.get(
                    "published_time",
                    metadata.get("published_time", ""),
                )
            ),
            raw_metadata=metadata,
        )

    @classmethod
    def _robots_document(cls, raw: Any) -> RobotsDocument:
        if not isinstance(raw, dict):
            return RobotsDocument(
                status_code=None,
                text="",
                content_ok=False,
                error="non_object_response",
            )
        status_value = raw.get(
            "status_code",
            raw.get("http_status", raw.get("status")),
        )
        try:
            status_code = int(status_value)
        except (TypeError, ValueError):
            status_code = None
        text = cls._normalize_content(
            raw.get("content", raw.get("text", raw.get("markdown", "")))
        )
        return RobotsDocument(
            status_code=status_code,
            text=text,
            content_ok=bool(raw.get("content_ok", status_code == 200)),
            error=str(raw.get("error", "")),
        )

    @staticmethod
    def _normalize_content(value: Any) -> str:
        if value is None:
            return ""
        if isinstance(value, str):
            return value
        if isinstance(value, list):
            parts: list[str] = []
            for item in value:
                if isinstance(item, str):
                    text = item
                else:
                    text = json.dumps(
                        item,
                        ensure_ascii=False,
                        sort_keys=True,
                    )
                if text.strip():
                    parts.append(text)
            return "\n\n".join(parts)
        if isinstance(value, dict):
            return json.dumps(
                value,
                ensure_ascii=False,
                sort_keys=True,
            )
        return str(value)

    @staticmethod
    def _hostname_matches_any_domain(
        hostname: str,
        domains: tuple[str, ...],
    ) -> bool:
        host = hostname.lower().rstrip(".")
        for domain in domains:
            allowed = domain.lower().rstrip(".")
            if host == allowed or host.endswith("." + allowed):
                return True
        return False

    @staticmethod
    def _normalize_warnings(value: Any) -> tuple[str, ...]:
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
    def _optional_float(value: Any) -> float | None:
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    def _audit(
        self,
        action: str,
        workflow_id: str,
        details: dict[str, Any],
    ) -> None:
        self.audit_sink(
            {
                "action": action,
                "status": (
                    "blocked"
                    if "blocked" in action
                    else "success"
                ),
                "workflow_id": workflow_id,
                "details": details,
            }
        )
