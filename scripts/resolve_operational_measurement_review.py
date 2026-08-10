#!/usr/bin/env python3
"""Resolve a human operational measurement review."""

from __future__ import annotations

import argparse
from pathlib import Path

from src.research.operational_measurement_review import (
    OperationalMeasurementReviewError,
    OperationalMeasurementReviewService,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--packet", required=True, type=Path)
    parser.add_argument("--decisions", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    try:
        resolution = OperationalMeasurementReviewService().resolve(
            packet_file=args.packet,
            decision_file=args.decisions,
            output_file=args.output,
        )
    except OperationalMeasurementReviewError as exc:
        parser.error(str(exc))

    print(f"Measurement review resolution: {args.output}")
    print(f"resolution_id: {resolution.resolution_id}")
    print(f"approved: {resolution.approved}")
    print(f"held: {resolution.held}")
    print(f"rejected: {resolution.rejected}")
    print("validation_log_import_allowed: false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
