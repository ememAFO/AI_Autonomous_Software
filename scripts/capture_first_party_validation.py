"""Capture sanitized Stage 4G first-party validation candidates."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.research.first_party_validation_capture import (
    FirstPartyCaptureError,
    FirstPartyCaptureService,
)
from src.research.first_party_validation_storage import (
    FirstPartyValidationStorageError,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Capture sanitized first-party validation candidates. "
            "This command does not modify the validation evidence log."
        )
    )
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--policy", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        report = FirstPartyCaptureService().capture(
            input_file=args.input,
            policy_file=args.policy,
            output_file=args.output,
        )
        print(f"Stage 4G capture complete: {args.output}")
        print(f"batch_id: {report['batch_id']}")
        print(f"received: {report['received']}")
        print(f"accepted: {report['accepted']}")
        print(f"blocked: {report['blocked']}")
        print(f"candidate_path: {report['candidate_path']}")
        return 0
    except (
        OSError,
        TypeError,
        ValueError,
        FirstPartyCaptureError,
        FirstPartyValidationStorageError,
    ) as exc:
        print(f"Stage 4G capture blocked: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
