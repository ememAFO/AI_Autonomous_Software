import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.hermes.validation_evidence_log import ValidationEvidenceLog
from src.hermes.validation_primary_evidence import (
    PrimaryEvidenceInput,
    ValidationPrimaryEvidenceError,
    ValidationPrimaryEvidenceLogger,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Add human-attested first-party validation evidence."
    )

    parser.add_argument("--theme", required=True)
    parser.add_argument("--validation-plan-path", required=True)
    parser.add_argument("--evidence-type", required=True)
    parser.add_argument("--participant-reference", required=True)
    parser.add_argument("--finding-summary", required=True)
    parser.add_argument("--source-reference", required=True)
    parser.add_argument("--signal-strength", required=True)
    parser.add_argument(
        "--supports-validation",
        action="store_true",
        help="Mark this first-party evidence as supporting the validation theme.",
    )
    parser.add_argument("--notes", default="")
    parser.add_argument(
        "--evidence-log-path",
        default="reports/intelligence/validation_evidence_log.json",
        help="Path to the validation evidence log JSON file.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    logger = ValidationPrimaryEvidenceLogger(
        ValidationEvidenceLog(log_path=args.evidence_log_path)
    )

    try:
        entry = logger.log_primary_evidence(
            PrimaryEvidenceInput(
                theme=args.theme,
                validation_plan_path=args.validation_plan_path,
                evidence_type=args.evidence_type,
                participant_reference=args.participant_reference,
                finding_summary=args.finding_summary,
                source_reference=args.source_reference,
                signal_strength=args.signal_strength,
                supports_validation=args.supports_validation,
                notes=args.notes,
            )
        )
    except ValidationPrimaryEvidenceError as exc:
        print(f"Primary evidence blocked: {exc}", file=sys.stderr)
        return 1

    print("\nPrimary Evidence Added")
    print("----------------------")
    print(f"Theme: {entry.theme}")
    print(f"Evidence Type: {entry.evidence_type}")
    print(f"Source Trust: {entry.source_trust}")
    print(f"Signal Strength: {entry.signal_strength}")
    print(f"Supports Validation: {entry.supports_validation}")
    print(f"Source Reference: {entry.source_reference}")
    print(f"Timestamp: {entry.timestamp}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
