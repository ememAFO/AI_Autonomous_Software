#!/usr/bin/env python3
"""Capture sanitized Stage 4G v0.2 operational measurements."""

from __future__ import annotations

import argparse
from pathlib import Path

from src.research.operational_measurement_capture import (
    OperationalMeasurementCaptureError,
    OperationalMeasurementCaptureService,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--policy", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    try:
        report = OperationalMeasurementCaptureService().capture(
            input_file=args.input,
            policy_file=args.policy,
            output_file=args.output,
        )
    except OperationalMeasurementCaptureError as exc:
        parser.error(str(exc))

    print(f"Operational measurement capture: {args.output}")
    print(f"accepted: {report['accepted']}")
    print(f"blocked: {report['blocked']}")
    print("validation_log_import_allowed: false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
