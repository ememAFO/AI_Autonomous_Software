import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.hermes.theme_state_registry import ThemeStateRegistry
from src.hermes.validation_evidence_log import ValidationEvidenceLog
from src.hermes.validation_evidence_summary import ValidationEvidenceSummarizer
from src.hermes.validation_progress_snapshot import (
    ValidationProgressSnapshotGenerator,
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
        description="Generate a read-only validation progress snapshot for a theme."
    )

    parser.add_argument("--theme-id", required=True)
    parser.add_argument("--theme-name", required=True)

    parser.add_argument(
        "--policy-version",
        default="2026-06-08.v1",
    )

    parser.add_argument(
        "--run-id",
        default="manual_validation_progress_snapshot",
    )

    parser.add_argument(
        "--state-registry-path",
        default="reports/intelligence/theme_state_registry.json",
    )

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
        "reports/intelligence/validation_progress_snapshots/"
        f"{slugify(args.theme_name)}_progress_snapshot.md"
    )

    generator = ValidationProgressSnapshotGenerator(
        state_registry=ThemeStateRegistry(
            registry_path=args.state_registry_path,
        ),
        evidence_summarizer=ValidationEvidenceSummarizer(
            ValidationEvidenceLog(log_path=args.evidence_log_path),
        ),
    )

    snapshot = generator.generate(
        theme_id=args.theme_id,
        theme_name=args.theme_name,
        policy_version=args.policy_version,
        run_id=args.run_id,
    )

    written_path = generator.write_markdown(
        snapshot=snapshot,
        output_path=output_path,
    )

    print("\nValidation Progress Snapshot Generated")
    print("--------------------------------------")
    print(f"Theme ID: {snapshot.theme_id}")
    print(f"Theme Name: {snapshot.theme_name}")
    print(f"Current State: {snapshot.current_state}")
    print(f"Evidence Status: {snapshot.evidence_status}")
    print(f"Gate Status: {snapshot.gate_status}")
    print(f"Gate Reason: {snapshot.gate_reason}")

    print(
        "Raw Total Evidence: "
        f"{snapshot.total_entries}/{snapshot.required_total_entries}"
    )
    print(
        "Raw Primary Evidence: "
        f"{snapshot.primary_entries}/{snapshot.required_primary_entries}"
    )

    print(f"Raw Secondary Evidence: {snapshot.secondary_entries}")
    print(f"Raw Risk Evidence: {snapshot.risk_entries}")

    print(
        "Gate-Safe Evidence: "
        f"{snapshot.gate_safe_entries}/{snapshot.required_total_entries}"
    )
    print(
        "Gate-Safe Primary Evidence: "
        f"{snapshot.gate_safe_primary_entries}/{snapshot.required_primary_entries}"
    )
    print(f"Gate-Safe Supporting Evidence: {snapshot.gate_safe_supporting_entries}")
    print(f"Suspect / Placeholder Evidence: {snapshot.suspect_entries}")

    print(f"Recommended Next Action: {snapshot.recommended_next_action}")
    print(f"Output Path: {written_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
