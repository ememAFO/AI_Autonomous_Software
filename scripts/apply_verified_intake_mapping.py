"""Apply a separately approved Stage 4F mapping."""

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
            "Append approved Stage 4F mappings to the validation "
            "evidence log."
        )
    )
    parser.add_argument("--packet", type=Path, required=True)
    parser.add_argument("--approval", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Required explicit authorization to append mapped entries.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        result = VerifiedIntakeMappingService().apply(
            packet_file=args.packet,
            approval_file=args.approval,
            output_file=args.output,
            apply_changes=args.apply,
        )
        print(f"Stage 4F import complete: {args.output}")
        print(f"imported: {result.imported}")
        print(f"held: {result.held}")
        print(f"rejected: {result.rejected}")
        print(
            "blocked_by_mapping_gate: "
            f"{result.blocked_by_mapping_gate}"
        )
        print(
            "before_status: "
            f"{result.before_summary['status']}"
        )
        print(
            "after_status: "
            f"{result.after_summary['status']}"
        )
        print(
            "after_gate_safe_primary_entries: "
            f"{result.after_summary['gate_safe_primary_entries']}"
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
            f"Stage 4F import blocked: {exc}",
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
