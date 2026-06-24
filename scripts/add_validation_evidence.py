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


PUBLIC_SOURCE_TRUST_CHOICES = (
    ValidationEvidenceLog.PUBLIC_DATASET,
    ValidationEvidenceLog.PUBLIC_COMPETITOR,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Add public validation research evidence. This command cannot "
            "record first-party customer evidence."
        )
    )

    parser.add_argument("--theme", required=True)
    parser.add_argument("--validation-plan-path", required=True)
    parser.add_argument(
        "--evidence-type",
        required=True,
        choices=sorted(ValidationEvidenceLog.ALLOWED_EVIDENCE_TYPES),
    )
    parser.add_argument(
        "--source-trust",
        required=True,
        choices=PUBLIC_SOURCE_TRUST_CHOICES,
        help=(
            "Use public_dataset for a dataset row or public_competitor for "
            "an official competitor source."
        ),
    )
    parser.add_argument("--evidence-summary", required=True)
    parser.add_argument("--source-reference", required=True)
    parser.add_argument(
        "--signal-strength",
        required=True,
        choices=sorted(ValidationEvidenceLog.ALLOWED_SIGNAL_STRENGTHS),
    )
    parser.add_argument(
        "--supports-validation",
        action="store_true",
        help="Mark this public evidence as supporting the validation theme.",
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
    evidence_log = ValidationEvidenceLog(log_path=args.evidence_log_path)

    try:
        entry = evidence_log.add_entry(
            theme=args.theme,
            validation_plan_path=args.validation_plan_path,
            evidence_type=args.evidence_type,
            evidence_summary=args.evidence_summary,
            source_reference=args.source_reference,
            signal_strength=args.signal_strength,
            supports_validation=args.supports_validation,
            source_trust=args.source_trust,
            notes=args.notes,
        )
    except ValidationEvidenceLogError as exc:
        print(f"Validation evidence blocked: {exc}", file=sys.stderr)
        return 1

    print("\nPublic Validation Evidence Added")
    print("--------------------------------")
    print(f"Theme: {entry.theme}")
    print(f"Evidence Type: {entry.evidence_type}")
    print(f"Source Trust: {entry.source_trust}")
    print(f"Signal Strength: {entry.signal_strength}")
    print(f"Supports Validation: {entry.supports_validation}")
    print(f"Timestamp: {entry.timestamp}")
    print(
        "Governance: public evidence can inform validation but cannot "
        "satisfy the first-party evidence requirement."
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
