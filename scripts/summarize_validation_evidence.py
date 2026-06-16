import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.hermes.validation_evidence_summary import ValidationEvidenceSummarizer


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Summarize validation evidence for a theme."
    )

    parser.add_argument("--theme", required=True)

    return parser.parse_args()


def format_pairs(values: list[tuple[str, int]], fallback: str) -> str:
    if not values:
        return fallback

    return "\n".join(f"- {name}: {count}" for name, count in values)


def main() -> int:
    args = parse_args()

    summary = ValidationEvidenceSummarizer().summarize_theme(args.theme)

    print("\nValidation Evidence Summary")
    print("---------------------------")
    print(f"Theme: {summary.theme}")
    print(f"Total Entries: {summary.total_entries}")
    print(f"Supporting Entries: {summary.supporting_entries}")
    print(f"Opposing Entries: {summary.opposing_entries}")
    print(f"Status: {summary.status}")
    print(f"Primary Entries: {summary.primary_entries}")
    print(f"Secondary Entries: {summary.secondary_entries}")
    print(f"Risk Entries: {summary.risk_entries}")
    print(f"Recommended Next Action: {summary.recommended_next_action}")

    print("\nSignal Strengths:")
    print(format_pairs(summary.signal_strengths, "- None recorded."))

    print("\nEvidence Types:")
    print(format_pairs(summary.evidence_types, "- None recorded."))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
