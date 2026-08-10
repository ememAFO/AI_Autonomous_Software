"""Prepare a read-only Stage 4F verified-intake mapping packet."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.research.verified_intake_mapping import (
    VerifiedIntakeMappingError,
    VerifiedIntakeMappingService,
)
from src.research.verified_intake_mapping_storage import (
    VerifiedIntakeMappingStorageError,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Prepare a Stage 4F mapping packet. This command does not "
            "modify the validation evidence log."
        )
    )
    parser.add_argument("--intake", type=Path, required=True)
    parser.add_argument("--resolution", type=Path, required=True)
    parser.add_argument("--policy", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--approval-template",
        type=Path,
        required=True,
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        packet = VerifiedIntakeMappingService().prepare(
            intake_file=args.intake,
            resolution_file=args.resolution,
            policy_file=args.policy,
            packet_output=args.output,
            approval_template_output=args.approval_template,
        )
        print(f"Stage 4F mapping packet prepared: {args.output}")
        print(f"packet_id: {packet.packet_id}")
        print(f"eligible: {packet.eligible_records}")
        print(f"blocked: {packet.blocked_records}")
        print(
            "proposed_primary_entries: "
            f"{packet.proposed_primary_entries}"
        )
        print(
            "proposed_secondary_entries: "
            f"{packet.proposed_secondary_entries}"
        )
        print(
            "proposed_risk_entries: "
            f"{packet.proposed_risk_entries}"
        )
        print(
            f"approval_template: {args.approval_template}"
        )
        return 0
    except (
        OSError,
        RuntimeError,
        TypeError,
        ValueError,
        VerifiedIntakeMappingError,
        VerifiedIntakeMappingStorageError,
    ) as exc:
        print(
            f"Stage 4F mapping preparation blocked: {exc}",
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
