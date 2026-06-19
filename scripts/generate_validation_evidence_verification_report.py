import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.hermes.validation_evidence_log import ValidationEvidenceLog
from src.hermes.validation_evidence_verification import (
    ValidationEvidenceVerificationError,
    ValidationEvidenceVerifier,
)


def slugify(value: str) -> str:
    return (
        value.lower()
        .replace("+", "and")
        .replace("/", "-")
        .replace(" ", "_")
        .replace("__", "_")
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate a read-only validation evidence verification report."
    )

    parser.add_argument("--theme", required=True)

    parser.add_argument(
        "--evidence-log-path",
        default="reports/intelligence/validation_evidence_log.json",
    )

    parser.add_argument(
        "--output-path",
        default=None,
    )

    return parser.parse_args()


def main() -> int:
    args = parse_args()

    output_path = args.output_path or (
        "reports/intelligence/validation_evidence_verification/"
        f"{slugify(args.theme)}_verification_report.md"
    )

    verifier = ValidationEvidenceVerifier(
        ValidationEvidenceLog(log_path=args.evidence_log_path)
    )

    try:
        report = verifier.generate(theme=args.theme)

        written_path = verifier.write_markdown(
            report=report,
            output_path=output_path,
        )
    except ValidationEvidenceVerificationError as exc:
        print(f"Validation evidence verification failed: {exc}", file=sys.stderr)
        return 1

    print("\nValidation Evidence Verification Report Generated")
    print("------------------------------------------------")
    print(f"Theme: {report.theme}")
    print(f"Total Evidence Entries: {report.total_entries}")
    print(f"Gate-Safe Evidence Entries: {report.gate_safe_entries}")
    print(f"Suspect / Placeholder Entries: {report.suspect_entries}")

    if report.findings:
        print("\nSuspect Entries:")
        for finding in report.findings:
            print(
                f"- Entry {finding.entry_index}: "
                f"{finding.evidence_type} | "
                f"{finding.source_reference} | "
                f"markers={', '.join(finding.matched_markers)}"
            )
    else:
        print("\nNo suspect entries detected.")

    print(f"\nOutput Path: {written_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
