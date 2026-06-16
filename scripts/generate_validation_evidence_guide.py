import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.hermes.validation_evidence_guide import ValidationEvidenceGuideGenerator


def slugify_theme(theme: str) -> str:
    return (
        theme.lower()
        .replace("+", "and")
        .replace("/", "-")
        .replace(" ", "_")
        .replace("__", "_")
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate a validation evidence collection guide for a theme."
    )

    parser.add_argument("--theme", required=True)

    parser.add_argument(
        "--output-path",
        default=None,
        help="Optional output Markdown path.",
    )

    return parser.parse_args()


def main() -> int:
    args = parse_args()

    output_path = args.output_path or (
        "reports/intelligence/validation_guides/"
        f"{slugify_theme(args.theme)}_evidence_guide.md"
    )

    generator = ValidationEvidenceGuideGenerator()
    written_path = generator.write_markdown(
        theme=args.theme,
        output_path=output_path,
    )

    guide = generator.generate(args.theme)

    print("\nValidation Evidence Guide Generated")
    print("-----------------------------------")
    print(f"Theme: {guide.theme}")
    print(f"Evidence Status: {guide.evidence_status}")
    print(f"Total Entries: {guide.total_entries}")
    print(f"Primary Entries: {guide.primary_entries}")
    print(f"Secondary Entries: {guide.secondary_entries}")
    print(f"Risk Entries: {guide.risk_entries}")
    print(f"Primary Entries Needed: {guide.primary_entries_needed}")
    print(f"Supporting Entries: {guide.supporting_entries}")
    print(f"Opposing Entries: {guide.opposing_entries}")
    print(f"Additional Entries Needed: {guide.additional_entries_needed}")
    print(f"Output Path: {written_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
