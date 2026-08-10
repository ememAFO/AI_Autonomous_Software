#!/usr/bin/env python3
"""Prepare a read-only operational measurement review packet."""

from __future__ import annotations

import argparse
from pathlib import Path

from src.research.operational_measurement_review import (
    OperationalMeasurementReviewError,
    OperationalMeasurementReviewService,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidates", required=True, type=Path)
    parser.add_argument("--policy", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument(
        "--decision-template",
        required=True,
        type=Path,
    )
    args = parser.parse_args()

    try:
        packet = OperationalMeasurementReviewService().prepare(
            candidate_file=args.candidates,
            policy_file=args.policy,
            packet_output=args.output,
            decision_template_output=args.decision_template,
        )
    except OperationalMeasurementReviewError as exc:
        parser.error(str(exc))

    print(f"Measurement review packet: {args.output}")
    print(f"packet_id: {packet.packet_id}")
    print(f"eligible: {packet.eligible_measurements}")
    print(f"blocked: {packet.blocked_measurements}")
    print("validation_log_import_allowed: false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
