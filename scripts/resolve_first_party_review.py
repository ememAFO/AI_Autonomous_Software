"""Resolve a human-reviewed Stage 4G first-party packet."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.research.first_party_validation_review import (
    FirstPartyReviewError,
    FirstPartyReviewService,
)
from src.research.first_party_validation_storage import (
    FirstPartyValidationStorageError,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Resolve a Stage 4G review packet into verified intake. "
            "This command does not modify the validation evidence log."
        )
    )
    parser.add_argument("--packet", type=Path, required=True)
    parser.add_argument("--decisions", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        result = FirstPartyReviewService().resolve(
            packet_file=args.packet,
            decision_file=args.decisions,
            output_file=args.output,
        )
        print(f"Stage 4G review resolved: {args.output}")
        print(f"resolution_id: {result.resolution_id}")
        print(f"approved: {result.approved}")
        print(f"held: {result.held}")
        print(f"rejected: {result.rejected}")
        print(f"blocked_by_gate: {result.blocked_by_gate}")
        print(f"verified_intake_path: {result.verified_intake_path}")
        return 0
    except (
        OSError,
        TypeError,
        ValueError,
        FirstPartyReviewError,
        FirstPartyValidationStorageError,
    ) as exc:
        print(f"Stage 4G review blocked: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
