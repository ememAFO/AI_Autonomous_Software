from src.adapters.hound_robots import (
    FailClosedRobotsChecker,
    RobotsDocument,
    RobotsStatus,
)


def test_404_robots_is_treated_as_absent() -> None:
    checker = FailClosedRobotsChecker()
    decision = checker.decide(
        "https://example.com/page",
        RobotsDocument(404, "", False),
    )
    assert decision.status is RobotsStatus.ALLOWED


def test_unavailable_robots_fails_closed() -> None:
    checker = FailClosedRobotsChecker()
    decision = checker.decide(
        "https://example.com/page",
        RobotsDocument(None, "", False, "timeout"),
    )
    assert decision.status is RobotsStatus.BLOCKED_UNKNOWN


def test_explicit_disallow_blocks() -> None:
    checker = FailClosedRobotsChecker()
    decision = checker.decide(
        "https://example.com/private",
        RobotsDocument(
            200,
            "User-agent: *\nDisallow: /private\n",
            True,
        ),
    )
    assert decision.status is RobotsStatus.BLOCKED


def test_explicit_allow_passes() -> None:
    checker = FailClosedRobotsChecker()
    decision = checker.decide(
        "https://example.com/public",
        RobotsDocument(
            200,
            "User-agent: *\nDisallow: /private\nAllow: /public\n",
            True,
        ),
    )
    assert decision.status is RobotsStatus.ALLOWED
