"""Prepare a read-only Stage 4G first-party review packet."""

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
            "Prepare a Stage 4G review packet. This command performs "
            "no evidence-log import."
        )
    )
    parser.add_argument("--candidates", type=Path, required=True)
    parser.add_argument("--policy", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--decision-template",
        type=Path,
        required=True,
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        packet = FirstPartyReviewService().prepare(
            candidate_file=args.candidates,
            policy_file=args.policy,
            packet_output=args.output,
            decision_template_output=args.decision_template,
        )
        print(f"Stage 4G review packet prepared: {args.output}")
        print(f"packet_id: {packet.packet_id}")
        print(f"eligible: {packet.eligible_candidates}")
        print(f"hold_only: {packet.hold_only_candidates}")
        print(f"blocked: {packet.blocked_candidates}")
        print(
            "proposed_primary_entries: "
            f"{packet.proposed_primary_entries}"
        )
        print(
            "proposed_risk_entries: "
            f"{packet.proposed_risk_entries}"
        )
        print(f"decision_template: {args.decision_template}")
        return 0
    except (
        OSError,
        TypeError,
        ValueError,
        FirstPartyReviewError,
        FirstPartyValidationStorageError,
    ) as exc:
        print(
            f"Stage 4G review preparation blocked: {exc}",
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
