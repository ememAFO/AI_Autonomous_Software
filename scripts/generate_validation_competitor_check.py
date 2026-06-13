import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.hermes.validation_competitor_check import (
    ValidationCompetitorCheckGenerator,
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
        description="Generate a competitor-check template for validation evidence collection."
    )

    parser.add_argument("--theme", required=True)

    parser.add_argument(
        "--target-user",
        default="small service business owner",
    )

    parser.add_argument(
        "--output-path",
        default=None,
    )

    return parser.parse_args()


def main() -> int:
    args = parse_args()

    output_path = args.output_path or (
        "reports/intelligence/validation_competitor_checks/"
        f"{slugify(args.theme)}_competitor_check.md"
    )

    generator = ValidationCompetitorCheckGenerator()

    written_path = generator.write_markdown(
        theme=args.theme,
        target_user=args.target_user,
        output_path=output_path,
    )

    print("\nValidation Competitor Check Generated")
    print("-------------------------------------")
    print(f"Theme: {args.theme}")
    print(f"Target User: {args.target_user}")
    print(f"Output Path: {written_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
