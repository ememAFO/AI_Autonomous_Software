"""Explicitly import reviewed Stage 4G first-party evidence."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.research.first_party_validation_import import (
    FirstPartyImportError,
    FirstPartyImportService,
)
from src.research.first_party_validation_storage import (
    FirstPartyValidationStorageError,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Append reviewed Stage 4G first-party evidence to the "
            "validation evidence log."
        )
    )
    parser.add_argument("--resolution", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--import-reference", required=True)
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Required explicit authorization to append evidence.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        result = FirstPartyImportService().apply(
            resolution_file=args.resolution,
            output_file=args.output,
            import_reference=args.import_reference,
            apply_changes=args.apply,
        )
        print(f"Stage 4G evidence import complete: {args.output}")
        print(f"import_id: {result.import_id}")
        print(f"imported: {result.imported}")
        print(f"before_status: {result.before_summary['status']}")
        print(f"after_status: {result.after_summary['status']}")
        print(
            "gate_safe_primary_before: "
            f"{result.before_summary['gate_safe_primary_entries']}"
        )
        print(
            "gate_safe_primary_after: "
            f"{result.after_summary['gate_safe_primary_entries']}"
        )
        return 0
    except (
        OSError,
        TypeError,
        ValueError,
        FirstPartyImportError,
        FirstPartyValidationStorageError,
    ) as exc:
        print(f"Stage 4G import blocked: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
