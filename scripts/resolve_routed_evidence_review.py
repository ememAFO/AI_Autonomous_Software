"""Resolve a Stage 4E packet using explicit human decisions."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

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
            "Resolve a Stage 4E review packet. Only APPROVE decisions "
            "enter the verified-intake queue."
        )
    )
    parser.add_argument("--packet", type=Path, required=True)
    parser.add_argument("--decisions", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        result = RoutedEvidenceReviewService().resolve(
            packet_file=args.packet,
            decision_file=args.decisions,
            output_path=args.output,
        )
        print(f"Stage 4E resolution complete: {args.output}")
        print(f"approved: {result.approved}")
        print(f"rejected: {result.rejected}")
        print(f"held: {result.held}")
        print(f"blocked_by_gate: {result.blocked_by_gate}")
        print(
            "verified_intake_path: "
            f"{result.verified_intake_path or 'none'}"
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
            f"Stage 4E resolution blocked: {exc}",
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
