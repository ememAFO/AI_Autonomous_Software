import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.hermes.memory_trend_detector import (
    HermesMemoryTrendDetector,
    MemoryTrendFilter,
)
from src.hermes.theme_validation_plan import (
    ThemeValidationPlanError,
    ThemeValidationPlanGenerator,
)
from src.hermes.theme_validation_readiness import ThemeValidationReadinessEvaluator


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate a validation plan for a validation-ready Hermes trend theme."
    )

    parser.add_argument(
        "--theme",
        required=True,
        help="Theme name to generate a validation plan for.",
    )

    parser.add_argument(
        "--industry",
        default=None,
        help="Optional industry filter.",
    )

    parser.add_argument(
        "--exclude-source",
        default=None,
        help="Optional source to exclude.",
    )

    return parser.parse_args()


def main() -> int:
    args = parse_args()

    summary = HermesMemoryTrendDetector().summarize(
        filters=MemoryTrendFilter(
            industry=args.industry,
            exclude_source=args.exclude_source,
        )
    )

    matching_theme = next(
        (
            theme for theme in summary.filtered_themes
            if theme.theme.lower() == args.theme.lower()
        ),
        None,
    )

    if matching_theme is None:
        print(f"Theme not found: {args.theme}", file=sys.stderr)
        return 1

    readiness = ThemeValidationReadinessEvaluator().evaluate(matching_theme)

    try:
        plan = ThemeValidationPlanGenerator().generate(readiness)
    except ThemeValidationPlanError as exc:
        print(f"Validation plan blocked: {exc}", file=sys.stderr)
        print(f"Theme: {readiness.theme}", file=sys.stderr)
        print(f"Readiness: {readiness.readiness}", file=sys.stderr)
        print(f"Reason: {readiness.reason}", file=sys.stderr)
        return 1

    print("\nValidation Plan Generated")
    print("-------------------------")
    print(f"Theme: {plan.theme}")
    print(f"Readiness: {plan.readiness}")
    print(f"Readiness Score: {plan.readiness_score}")
    print(f"Output Path: {plan.output_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
