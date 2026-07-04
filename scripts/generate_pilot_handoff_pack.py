import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.hermes.pilot_handoff_pack import (
    PilotHandoffPackError,
    PilotHandoffPackGenerator,
)
from src.hermes.validation_evidence_log import (
    ValidationEvidenceLog,
    ValidationEvidenceLogError,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Generate a read-only future pilot handoff pack. "
            "This does not start a pilot or approve build work."
        )
    )
    parser.add_argument("--theme", required=True)
    parser.add_argument(
        "--evidence-log-path",
        default="reports/intelligence/validation_evidence_log.json",
    )
    parser.add_argument("--output-path", default=None)
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    try:
        generator = PilotHandoffPackGenerator(
            evidence_log=ValidationEvidenceLog(
                log_path=args.evidence_log_path
            )
        )
        pack, written_path = generator.generate(
            theme=args.theme,
            output_path=args.output_path,
        )
    except (
        PilotHandoffPackError,
        ValidationEvidenceLogError,
    ) as exc:
        print(f"Pilot handoff pack blocked: {exc}", file=sys.stderr)
        return 1

    print("\nPilot Handoff Pack Generated")
    print("-----------------------------")
    print(f"Theme: {pack.theme}")
    print(f"Pilot Status: {pack.pilot_status}")
    print(f"Validation Evidence Status: {pack.evidence_status}")
    print(
        "Gate-Safe Public Research Entries: "
        f"{pack.gate_safe_public_research_entries}"
    )
    print(
        "Gate-Safe First-Party Primary Entries: "
        f"{pack.gate_safe_first_party_primary_entries}"
    )
    print(
        "Decision Boundary: Future pilot handoff only; "
        "no business has been enrolled and no MVP work is approved."
    )
    print(f"Output Path: {written_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
