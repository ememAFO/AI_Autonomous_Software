"""Run the Stage 4C Hound benchmark under the factory safety wrapper.

Run 2 measures two distinct capabilities:
1. Discovery recall: can Hound search recover the frozen sources?
2. Known-URL retrieval: can Hound safely fetch sources already known?

The script creates an evidence-candidate queue and a run report. It does not
modify the approved evidence registry or perform any public action.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.adapters.hound_adapter import (
    HoundAdapterError,
    HoundResearchAdapter,
)
from src.adapters.hound_policy import (
    HoundPilotPolicy,
    HoundPolicyError,
)
from src.adapters.hound_transport import (
    HoundTransportError,
    MCPStdioTransport,
)
from src.adapters.research_adapter import (
    CandidateStatus,
    EvidenceCandidate,
    FetchRequest,
    SearchRequest,
)
from src.research.evidence_candidate_queue import EvidenceCandidateQueue

try:
    from src.utils.audit_logger import AuditEvent, AuditLogger
except ImportError:  # pragma: no cover
    AuditEvent = None
    AuditLogger = None


EXPECTED_OPERATIONAL_ERRORS = (
    HoundAdapterError,
    HoundPolicyError,
    HoundTransportError,
    OSError,
    RuntimeError,
    TypeError,
    ValueError,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the governed EOP-0001 Hound benchmark."
    )
    parser.add_argument(
        "--profile",
        type=Path,
        default=Path("config/hound_pilot_safety_profile.json"),
    )
    parser.add_argument(
        "--plan",
        type=Path,
        default=Path("config/hound_live_benchmark_test_plan.json"),
    )
    parser.add_argument(
        "--registry",
        type=Path,
        default=Path(
            "data/eop/EOP-0001_Evidence_Registry_v1.0.json"
        ),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(
            "reports/hound/eop-0001-benchmark-run-2.json"
        ),
    )
    parser.add_argument(
        "--hound-command",
        nargs="+",
        default=["hound"],
    )
    return parser.parse_args()


def load_object(path: Path) -> dict[str, Any]:
    if not path.exists() or not path.is_file():
        raise ValueError(f"Required file does not exist: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise TypeError(f"Expected JSON object in {path}")
    return data


def make_audit_sink():
    if AuditLogger is None or AuditEvent is None:
        return lambda event: None

    logger = AuditLogger()

    def sink(event: dict[str, Any]) -> None:
        logger.log(
            AuditEvent(
                action=str(
                    event.get("action", "hound_benchmark")
                ),
                status=str(event.get("status", "success")),
                details={
                    "workflow_id": event.get("workflow_id", ""),
                    **dict(event.get("details", {})),
                },
            )
        )

    return sink


def canonical_key(url: str) -> tuple[str, str]:
    parsed = urlsplit(url)
    host = (parsed.hostname or "").lower()
    path = parsed.path.rstrip("/") or "/"
    return host, path


def candidate_payload(
    candidate: EvidenceCandidate,
    queue_path: Path,
) -> dict[str, Any]:
    return {
        **asdict(candidate),
        "status": candidate.status.value,
        "queue_path": str(queue_path),
    }


def main() -> int:
    args = parse_args()
    try:
        profile = load_object(args.profile)
        plan = load_object(args.plan)
        registry = load_object(args.registry)

        domain_config = profile["domain_policy"]
        request_config = profile["research_mode"]["request_limits"]
        policy = HoundPilotPolicy(
            domain_config["allowlist"],
            allow_subdomains=bool(
                domain_config.get("allow_subdomains", True)
            ),
            max_results=int(
                request_config["search_results_per_query"]
            ),
            max_fetches_per_workflow=int(
                request_config["total_fetches_per_workflow"]
            ),
            max_content_chars=int(
                request_config["max_content_chars"]
            ),
        )

        expected_records = {
            str(item["evidence_id"]): {
                "url": str(item["url"]),
                "claim_supported": str(
                    item.get("claim_supported", "")
                ),
            }
            for item in registry.get("evidence", [])
            if isinstance(item, dict)
            and item.get("evidence_id")
            and item.get("url")
        }
        expected_keys = {
            evidence_id: canonical_key(record["url"])
            for evidence_id, record in expected_records.items()
        }

        run_id = (
            "HOUND-EOP-0001-RUN2-"
            + datetime.now(timezone.utc).strftime(
                "%Y%m%dT%H%M%SZ"
            )
        )
        queue = EvidenceCandidateQueue()
        audit_sink = make_audit_sink()
        discovery_records: list[dict[str, Any]] = []
        direct_fetch_records: list[dict[str, Any]] = []
        discovered: set[str] = set()
        direct_fetch_success: set[str] = set()

        with MCPStdioTransport(args.hound_command) as transport:
            adapter = HoundResearchAdapter(
                transport,
                policy,
                audit_sink=audit_sink,
            )

            # Phase A: discovery benchmark.
            for query_item in plan.get("query_set", []):
                query_id = str(query_item["query_id"])
                target_domains = tuple(
                    query_item.get("target_domains", [])
                )
                request = SearchRequest(
                    workflow_id=run_id,
                    query=str(query_item["query"]),
                    allowed_domains=target_domains,
                    max_results=int(
                        request_config[
                            "search_results_per_query"
                        ]
                    ),
                )
                search_results = adapter.search(request)
                fetched = 0

                for result in search_results:
                    record: dict[str, Any] = {
                        "query_id": query_id,
                        "search_result": asdict(result),
                        "candidate": None,
                        "error": "",
                    }
                    if not result.allowed_to_fetch:
                        record["error"] = "blocked_by_policy"
                        discovery_records.append(record)
                        continue
                    if fetched >= int(
                        request_config[
                            "fetched_urls_per_query"
                        ]
                    ):
                        record["error"] = (
                            "per_query_fetch_limit"
                        )
                        discovery_records.append(record)
                        continue

                    try:
                        candidate = adapter.fetch(
                            FetchRequest(
                                workflow_id=run_id,
                                url=result.url,
                                focus=str(query_item["query"]),
                                max_content_chars=int(
                                    request_config[
                                        "max_content_chars"
                                    ]
                                ),
                            )
                        )
                        queue_path = queue.append(candidate)
                        record["candidate"] = candidate_payload(
                            candidate,
                            queue_path,
                        )
                        candidate_key = canonical_key(
                            candidate.canonical_url
                        )
                        for (
                            evidence_id,
                            expected_key,
                        ) in expected_keys.items():
                            if candidate_key == expected_key:
                                discovered.add(evidence_id)
                        fetched += 1
                    except EXPECTED_OPERATIONAL_ERRORS as exc:
                        record["error"] = (
                            f"{type(exc).__name__}: {exc}"
                        )
                    discovery_records.append(record)

            # Phase B: direct known-URL retrieval benchmark.
            for evidence_id, expected in expected_records.items():
                record: dict[str, Any] = {
                    "evidence_id": evidence_id,
                    "url": expected["url"],
                    "candidate": None,
                    "error": "",
                }
                try:
                    candidate = adapter.fetch(
                        FetchRequest(
                            workflow_id=run_id,
                            url=expected["url"],
                            focus=expected["claim_supported"] or None,
                            max_content_chars=int(
                                request_config[
                                    "max_content_chars"
                                ]
                            ),
                        )
                    )
                    queue_path = queue.append(candidate)
                    record["candidate"] = candidate_payload(
                        candidate,
                        queue_path,
                    )
                    if (
                        candidate.content_ok
                        and candidate.status
                        is CandidateStatus.CANDIDATE
                    ):
                        direct_fetch_success.add(evidence_id)
                except EXPECTED_OPERATIONAL_ERRORS as exc:
                    record["error"] = (
                        f"{type(exc).__name__}: {exc}"
                    )
                direct_fetch_records.append(record)

            health = asdict(adapter.health())

        retained_sources = int(
            plan["benchmark_reference"]["retained_sources"]
        )
        discovery_recall = (
            len(discovered) / retained_sources
            if retained_sources
            else 0.0
        )
        known_url_success_rate = (
            len(direct_fetch_success) / retained_sources
            if retained_sources
            else 0.0
        )
        direct_failures = [
            record["evidence_id"]
            for record in direct_fetch_records
            if record["evidence_id"]
            not in direct_fetch_success
        ]

        report = {
            "run_id": run_id,
            "started_and_completed_at": (
                datetime.now(timezone.utc).isoformat()
            ),
            "status": "awaiting_human_candidate_review",
            "adapter_health": health,
            "discovery": {
                "recovered_evidence_ids": sorted(discovered),
                "recall_exact_url": discovery_recall,
                "records": discovery_records,
            },
            "known_url_fetch": {
                "successful_evidence_ids": sorted(
                    direct_fetch_success
                ),
                "failed_evidence_ids": direct_failures,
                "success_rate": known_url_success_rate,
                "records": direct_fetch_records,
            },
            "precision": None,
            "precision_note": (
                "Requires human review labels. The runner does "
                "not approve evidence automatically."
            ),
            "protected_actions": {
                "approved_registry_modified": False,
                "public_action_taken": False,
                "automatic_outreach": False,
            },
        }

        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(
                report,
                indent=2,
                ensure_ascii=False,
            )
            + "\n",
            encoding="utf-8",
        )
        print(f"Hound Run 2 complete: {args.output}")
        print(
            "Discovery exact-URL recall: "
            f"{discovery_recall:.1%}"
        )
        print(
            "Known-URL HTTP fetch success: "
            f"{known_url_success_rate:.1%}"
        )
        return 0
    except EXPECTED_OPERATIONAL_ERRORS + (
        KeyError,
        json.JSONDecodeError,
    ) as exc:
        print(
            f"Hound Run 2 blocked: {exc}",
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
