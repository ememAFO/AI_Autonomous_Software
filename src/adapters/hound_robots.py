"""Fail-closed robots policy.

The factory checks robots.txt before requesting page content. Hound's internal
robots result is treated as defence-in-depth only because Hound currently
fails open on some robots retrieval/parser failures.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from urllib.parse import urlsplit, urlunsplit
from urllib.robotparser import RobotFileParser


class RobotsStatus(str, Enum):
    ALLOWED = "allowed"
    BLOCKED = "blocked"
    BLOCKED_UNKNOWN = "blocked_unknown"


@dataclass(frozen=True)
class RobotsDocument:
    status_code: int | None
    text: str
    content_ok: bool
    error: str = ""


@dataclass(frozen=True)
class RobotsDecision:
    status: RobotsStatus
    robots_url: str
    reason: str


class FailClosedRobotsChecker:
    def __init__(self, *, user_agent: str = "AI-Software-Factory-Research/0.1"):
        self.user_agent = user_agent

    @staticmethod
    def robots_url_for(url: str) -> str:
        parsed = urlsplit(url)
        return urlunsplit((parsed.scheme, parsed.netloc, "/robots.txt", "", ""))

    def decide(self, target_url: str, document: RobotsDocument) -> RobotsDecision:
        robots_url = self.robots_url_for(target_url)

        # RFC-style absence: an explicit 404/410 means no robots rules exist.
        if document.status_code in {404, 410}:
            return RobotsDecision(
                RobotsStatus.ALLOWED,
                robots_url,
                "robots_absent",
            )

        if document.status_code != 200 or not document.content_ok:
            detail = document.error or f"status={document.status_code}"
            return RobotsDecision(
                RobotsStatus.BLOCKED_UNKNOWN,
                robots_url,
                f"robots_unavailable:{detail}",
            )

        if not document.text.strip():
            return RobotsDecision(
                RobotsStatus.BLOCKED_UNKNOWN,
                robots_url,
                "robots_empty_or_unparseable",
            )

        parser = RobotFileParser()
        parser.set_url(robots_url)
        try:
            parser.parse(document.text.splitlines())
            allowed = parser.can_fetch(self.user_agent, target_url)
        except Exception as exc:  # noqa: BLE001  # pragma: no cover - fail-closed parser boundary
            return RobotsDecision(
                RobotsStatus.BLOCKED_UNKNOWN,
                robots_url,
                f"robots_parse_error:{exc}",
            )

        if not allowed:
            return RobotsDecision(
                RobotsStatus.BLOCKED,
                robots_url,
                "robots_explicit_disallow",
            )
        return RobotsDecision(RobotsStatus.ALLOWED, robots_url, "robots_allows")
