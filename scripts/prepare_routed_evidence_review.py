"""Prepare a Stage 4E evidence review packet from a Stage 4D routing run."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.research.routed_evidence_review import (
    RoutedEvidenceReviewError,
    RoutedEvidenceReviewService,
)
from src.research.routed_evidence_review_storage import (
    RoutedEvidenceReviewStorageError,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Prepare a read-only Stage 4E routed evidence review packet."
        )
    )
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument(
        "--routing-report",
        type=Path,
        help="Stage 4D routing report containing run_id.",
    )
    source.add_argument(
        "--candidate-file",
        type=Path,
        help="Candidate JSONL inside data/research/evidence_candidates.",
    )
    parser.add_argument(
        "--workflow-id",
        default="",
        help="Required with --candidate-file; inferred from routing report.",
    )
    parser.add_argument(
        "--output-prefix",
        type=Path,
        default=None,
        help=(
            "Output prefix inside reports/research/"
            "evidence_review_packets."
        ),
    )
    return parser.parse_args()


def load_object(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RoutedEvidenceReviewError(
            f"Could not read routing report: {path}"
        ) from exc
    if not isinstance(data, dict):
        raise RoutedEvidenceReviewError(
            "Routing report must contain a JSON object"
        )
    return data


def main() -> int:
    args = parse_args()
    try:
        if args.routing_report:
            report = load_object(args.routing_report)
            workflow_id = str(report.get("run_id", "")).strip()
            if not workflow_id:
                raise RoutedEvidenceReviewError(
                    "Routing report has no run_id"
                )
            candidate_file = Path(
                "data/research/evidence_candidates"
            ) / f"{workflow_id}.jsonl"
        else:
            workflow_id = args.workflow_id.strip()
            if not workflow_id:
                raise RoutedEvidenceReviewError(
                    "--workflow-id is required with --candidate-file"
                )
            candidate_file = args.candidate_file

        safe_workflow = "".join(
            character
            for character in workflow_id
            if character.isalnum() or character in {"-", "_"}
        )
        output_prefix = args.output_prefix or (
            Path("reports/research/evidence_review_packets")
            / safe_workflow
        )
        packet = RoutedEvidenceReviewService().prepare_packet(
            workflow_id=workflow_id,
            candidate_file=candidate_file,
            output_json=output_prefix.with_suffix(".json"),
            output_markdown=output_prefix.with_suffix(".md"),
            decision_template=output_prefix.with_name(
                output_prefix.name + "-decision-template"
            ).with_suffix(".json"),
        )
        print(
            "Stage 4E review packet prepared: "
            f"{output_prefix.with_suffix('.json')}"
        )
        print(f"packet_id: {packet.packet_id}")
        print(f"eligible: {packet.eligible_candidates}")
        print(f"blocked: {packet.blocked_candidates}")
        print(f"duplicates: {packet.duplicate_candidates}")
        print(
            "decision_template: "
            f"{output_prefix.with_name(output_prefix.name + '-decision-template').with_suffix('.json')}"
        )
        return 0
    except (
        OSError,
        RuntimeError,
        TypeError,
        ValueError,
        RoutedEvidenceReviewError,
        RoutedEvidenceReviewStorageError,
    ) as exc:
        print(
            f"Stage 4E packet preparation blocked: {exc}",
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
