"""Factory-owned safety policy for the Hound research adapter."""

from __future__ import annotations

import ipaddress
import re
from collections.abc import Iterable
from dataclasses import dataclass
from urllib.parse import urlsplit


class HoundPolicyError(ValueError):
    """Raised when a request violates the pilot policy."""


@dataclass(frozen=True)
class URLDecision:
    allowed: bool
    hostname: str
    reason: str


class HoundPilotPolicy:
    """Fail-closed policy applied before and after every Hound tool call."""

    _INJECTION_PATTERNS = (
        r"\bignore (all |any |the )?(previous|prior|system|developer) instructions?\b",
        r"\breveal (the )?(system prompt|developer message|environment variables?|secrets?|credentials?)\b",
        r"\b(fetch|open|request|connect to) (localhost|127\.0\.0\.1|0\.0\.0\.0|169\.254\.169\.254)\b",
        r"\b(disable|ignore|bypass) robots(\.txt)?\b",
        r"\b(call|invoke|use) (the )?(tool|shell|terminal|browser)\b",
        r"\bsend (me |us )?(your )?(api key|token|password|secret)\b",
        r"\boverride (the )?(policy|allowlist|approval|scope)\b",
    )

    def __init__(
        self,
        allowlist: Iterable[str],
        *,
        allow_subdomains: bool = True,
        max_results: int = 10,
        max_fetches_per_workflow: int = 40,
        max_content_chars: int = 40_000,
    ) -> None:
        normalized = {
            self._normalize_domain(domain)
            for domain in allowlist
            if str(domain).strip()
        }
        if not normalized:
            raise HoundPolicyError("Domain allowlist cannot be empty")
        if max_results < 1 or max_results > 25:
            raise HoundPolicyError("max_results must be between 1 and 25")
        if max_fetches_per_workflow < 1 or max_fetches_per_workflow > 100:
            raise HoundPolicyError(
                "max_fetches_per_workflow must be between 1 and 100"
            )
        if max_content_chars < 1_000 or max_content_chars > 100_000:
            raise HoundPolicyError(
                "max_content_chars must be between 1,000 and 100,000"
            )

        self.allowlist = frozenset(normalized)
        self.allow_subdomains = allow_subdomains
        self.max_results = max_results
        self.max_fetches_per_workflow = max_fetches_per_workflow
        self.max_content_chars = max_content_chars

    @staticmethod
    def _normalize_domain(domain: str) -> str:
        value = str(domain).strip().lower().rstrip(".")
        if "://" in value:
            parsed = urlsplit(value)
            value = (parsed.hostname or "").lower().rstrip(".")
        if not value or "/" in value or "@" in value:
            raise HoundPolicyError(f"Invalid allowlist domain: {domain!r}")
        return value

    def is_domain_allowed(self, hostname: str) -> bool:
        host = self._normalize_domain(hostname)
        if host in self.allowlist:
            return True
        if not self.allow_subdomains:
            return False
        return any(host.endswith("." + allowed) for allowed in self.allowlist)

    def check_url(self, url: str) -> URLDecision:
        try:
            parsed = urlsplit(str(url).strip())
        except ValueError as exc:
            return URLDecision(False, "", f"invalid_url:{exc}")

        if parsed.scheme not in {"http", "https"}:
            return URLDecision(False, "", "blocked_scheme")
        if parsed.username or parsed.password:
            return URLDecision(False, "", "userinfo_not_allowed")
        hostname = (parsed.hostname or "").lower().rstrip(".")
        if not hostname:
            return URLDecision(False, "", "missing_hostname")

        try:
            ip = ipaddress.ip_address(hostname)
        except ValueError:
            ip = None
        if ip is not None and (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_multicast
            or ip.is_reserved
            or ip.is_unspecified
        ):
            return URLDecision(False, hostname, "blocked_ip_range")

        if hostname in {"localhost", "metadata.google.internal"}:
            return URLDecision(False, hostname, "blocked_local_or_metadata_host")
        if not self.is_domain_allowed(hostname):
            return URLDecision(False, hostname, "domain_not_allowlisted")
        return URLDecision(True, hostname, "allowed")

    def validate_search_request(
        self,
        *,
        workflow_id: str,
        query: str,
        allowed_domains: tuple[str, ...],
        max_results: int,
    ) -> None:
        if not workflow_id.strip():
            raise HoundPolicyError("workflow_id cannot be empty")
        query_value = query.strip()
        if not query_value:
            raise HoundPolicyError("query cannot be empty")
        if len(query_value) > 500:
            raise HoundPolicyError("query exceeds 500 characters")
        if max_results < 1 or max_results > self.max_results:
            raise HoundPolicyError(
                f"max_results cannot exceed policy maximum {self.max_results}"
            )
        if not allowed_domains:
            raise HoundPolicyError("Search must declare at least one domain")
        for domain in allowed_domains:
            if not self.is_domain_allowed(domain):
                raise HoundPolicyError(
                    f"Search domain is not allowlisted: {domain}"
                )

    def scan_untrusted_content(self, text: str) -> tuple[str, ...]:
        findings: list[str] = []
        sample = text[: self.max_content_chars]
        for pattern in self._INJECTION_PATTERNS:
            if re.search(pattern, sample, flags=re.IGNORECASE):
                findings.append(f"prompt_injection_pattern:{pattern}")
        return tuple(findings)
