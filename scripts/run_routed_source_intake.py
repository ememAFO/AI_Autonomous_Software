"""Run Stage 4D governed source routing.

Input may be a generic source manifest or a frozen evidence registry. Reddit
URLs without supplied public post content are sent to human review; they are
never escalated to Hound browser mode.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.adapters.hound_adapter import HoundResearchAdapter
from src.adapters.hound_policy import HoundPilotPolicy
from src.adapters.hound_transport import MCPStdioTransport
from src.adapters.reddit_adapter import RedditPost
from src.research.research_adapter_router import (
    ResearchAdapterRouter,
    RoutedSourceRequest,
)
from src.utils.audit_logger import AuditEvent, AuditLogger


class RoutedSourceIntakeError(ValueError):
    """Raised when Stage 4D input is missing or malformed."""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Route public research sources through governed adapters."
    )
    source_group = parser.add_mutually_exclusive_group(required=True)
    source_group.add_argument("--manifest", type=Path)
    source_group.add_argument("--registry", type=Path)
    parser.add_argument(
        "--industry",
        default="home services",
        help="Required for supplied Reddit post processing.",
    )
    parser.add_argument(
        "--profile",
        type=Path,
        default=Path("config/hound_pilot_safety_profile.json"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("reports/research/stage4d-routing-run.json"),
    )
    parser.add_argument(
        "--hound-command",
        nargs="+",
        default=["hound"],
    )
    return parser.parse_args()


def load_object(path: Path) -> dict[str, Any]:
    if not path.exists() or not path.is_file():
        raise RoutedSourceIntakeError(
            f"Required file does not exist: {path}"
        )
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise RoutedSourceIntakeError(
            f"Expected JSON object in {path}"
        )
    return data


def requests_from_manifest(
    data: dict[str, Any],
    *,
    default_industry: str,
) -> list[RoutedSourceRequest]:
    workflow_id = str(data.get("workflow_id", "")).strip()
    sources = data.get("sources", [])
    if not workflow_id:
        raise RoutedSourceIntakeError(
            "Manifest workflow_id cannot be empty"
        )
    if not isinstance(sources, list) or not sources:
        raise RoutedSourceIntakeError(
            "Manifest sources must be a non-empty list"
        )

    requests: list[RoutedSourceRequest] = []
    for raw in sources:
        if not isinstance(raw, dict):
            raise RoutedSourceIntakeError(
                "Every manifest source must be an object"
            )
        reddit_data = raw.get("reddit_post")
        reddit_post = None
        if reddit_data is not None:
            if not isinstance(reddit_data, dict):
                raise RoutedSourceIntakeError(
                    "reddit_post must be an object"
                )
            reddit_post = RedditPost(
                subreddit=str(reddit_data.get("subreddit", "")),
                title=str(reddit_data.get("title", "")),
                body=str(reddit_data.get("body", "")),
                url=str(
                    reddit_data.get("url", raw.get("url", ""))
                ),
            )
        requests.append(
            RoutedSourceRequest(
                workflow_id=workflow_id,
                source_id=str(raw.get("source_id", "")),
                url=str(raw.get("url", "")),
                focus=str(raw.get("focus", "")),
                industry=str(
                    raw.get("industry", default_industry)
                ),
                reddit_post=reddit_post,
            )
        )
    return requests


def requests_from_registry(
    data: dict[str, Any],
    *,
    industry: str,
) -> list[RoutedSourceRequest]:
    registry_id = str(data.get("registry_id", "registry")).strip()
    evidence = data.get("evidence", [])
    if not isinstance(evidence, list) or not evidence:
        raise RoutedSourceIntakeError(
            "Registry evidence must be a non-empty list"
        )
    workflow_id = (
        f"{registry_id}-STAGE4D-"
        + datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    )
    requests: list[RoutedSourceRequest] = []
    for item in evidence:
        if not isinstance(item, dict):
            continue
        requests.append(
            RoutedSourceRequest(
                workflow_id=workflow_id,
                source_id=str(item.get("evidence_id", "")),
                url=str(item.get("url", "")),
                focus=str(item.get("claim_supported", "")),
                industry=industry,
            )
        )
    if not requests:
        raise RoutedSourceIntakeError(
            "Registry contains no routable evidence records"
        )
    return requests


def build_policy(profile: dict[str, Any]) -> HoundPilotPolicy:
    domain_config = profile["domain_policy"]
    limits = profile["research_mode"]["request_limits"]
    return HoundPilotPolicy(
        domain_config["allowlist"],
        allow_subdomains=bool(
            domain_config.get("allow_subdomains", True)
        ),
        max_results=int(limits["search_results_per_query"]),
        max_fetches_per_workflow=int(
            limits["total_fetches_per_workflow"]
        ),
        max_content_chars=int(limits["max_content_chars"]),
    )


def make_audit_sink():
    logger = AuditLogger()

    def sink(event: dict[str, object]) -> None:
        logger.log(
            AuditEvent(
                action=str(event.get("action", "source_routed")),
                status=str(event.get("status", "unknown")),
                details=dict(event.get("details", {})),
            )
        )

    return sink


def main() -> int:
    args = parse_args()
    try:
        profile = load_object(args.profile)
        if args.manifest:
            requests = requests_from_manifest(
                load_object(args.manifest),
                default_industry=args.industry,
            )
            input_path = args.manifest
            input_type = "manifest"
        else:
            requests = requests_from_registry(
                load_object(args.registry),
                industry=args.industry,
            )
            input_path = args.registry
            input_type = "registry"

        with MCPStdioTransport(args.hound_command) as transport:
            router = ResearchAdapterRouter(
                hound_adapter=HoundResearchAdapter(
                    transport,
                    build_policy(profile),
                    audit_sink=make_audit_sink(),
                ),
                audit_sink=make_audit_sink(),
            )
            results = [router.route(request) for request in requests]

        counts: dict[str, int] = {}
        for result in results:
            counts[result.status.value] = (
                counts.get(result.status.value, 0) + 1
            )
        report = {
            "run_id": requests[0].workflow_id,
            "completed_at": datetime.now(UTC).isoformat(),
            "input_type": input_type,
            "input_path": str(input_path),
            "result_counts": counts,
            "results": [asdict(result) for result in results],
            "protected_actions": {
                "approved_registry_modified": False,
                "public_action_taken": False,
                "automatic_outreach": False,
                "browser_or_stealth_enabled": False,
            },
        }
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(report, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        print(f"Stage 4D routing complete: {args.output}")
        for status, count in sorted(counts.items()):
            print(f"{status}: {count}")
        return 0
    except (
        KeyError,
        OSError,
        RuntimeError,
        TypeError,
        ValueError,
        json.JSONDecodeError,
    ) as exc:
        print(f"Stage 4D routing blocked: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
