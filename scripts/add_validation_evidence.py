import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.hermes.validation_evidence_log import (
    ValidationEvidenceLog,
    ValidationEvidenceLogError,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Add validation evidence for a validation plan."
    )

    parser.add_argument("--theme", required=True)
    parser.add_argument("--validation-plan-path", required=True)
    parser.add_argument("--evidence-type", required=True)
    parser.add_argument("--evidence-summary", required=True)
    parser.add_argument("--source-reference", required=True)
    parser.add_argument("--signal-strength", required=True)
    parser.add_argument(
        "--supports-validation",
        action="store_true",
        help="Mark this evidence as supporting validation.",
    )
    parser.add_argument("--notes", default="")

    return parser.parse_args()


def main() -> int:
    args = parse_args()

    try:
        entry = ValidationEvidenceLog().add_entry(
            theme=args.theme,
            validation_plan_path=args.validation_plan_path,
            evidence_type=args.evidence_type,
            evidence_summary=args.evidence_summary,
            source_reference=args.source_reference,
            signal_strength=args.signal_strength,
            supports_validation=args.supports_validation,
            notes=args.notes,
        )
    except ValidationEvidenceLogError as exc:
        print(f"Validation evidence blocked: {exc}", file=sys.stderr)
        return 1

    print("\nValidation Evidence Added")
    print("-------------------------")
    print(f"Theme: {entry.theme}")
    print(f"Evidence Type: {entry.evidence_type}")
    print(f"Signal Strength: {entry.signal_strength}")
    print(f"Supports Validation: {entry.supports_validation}")
    print(f"Timestamp: {entry.timestamp}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
