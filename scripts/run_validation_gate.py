import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.hermes.theme_state_registry import ThemeStateRegistry, ThemeStateRegistryError
from src.hermes.validation_evidence_log import ValidationEvidenceLog
from src.hermes.validation_evidence_summary import ValidationEvidenceSummarizer
from src.hermes.validation_gate import ValidationGate, ValidationGateError

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the validation gate for a theme."
    )

    parser.add_argument("--theme-id", required=True)
    parser.add_argument("--theme-name", required=True)

    parser.add_argument(
        "--policy-version",
        default="2026-06-08.v1",
    )

    parser.add_argument(
        "--run-id",
        default="manual_validation_gate_run",
    )

    parser.add_argument(
        "--related-artifact-id",
        default="validation_evidence_summary",
    )

    parser.add_argument(
        "--state-registry-path",
        default="reports/intelligence/theme_state_registry.json",
        help="Path to the theme state registry JSON file.",
    )

    parser.add_argument(
        "--evidence-log-path",
        default="reports/intelligence/validation_evidence_log.json",
        help="Path to the validation evidence log JSON file.",
    )

    return parser.parse_args()


def main() -> int:
    args = parse_args()

    try:
        gate = ValidationGate(
            state_registry=ThemeStateRegistry(
                registry_path=args.state_registry_path
            ),
            evidence_summarizer=ValidationEvidenceSummarizer(
                ValidationEvidenceLog(log_path=args.evidence_log_path)
            ),
        )

        result = gate.evaluate(
            theme_id=args.theme_id,
            theme_name=args.theme_name,
            policy_version=args.policy_version,
            run_id=args.run_id,
            related_artifact_id=args.related_artifact_id,
        )

    except (ThemeStateRegistryError, ValidationGateError) as exc:
        print(f"Validation gate failed: {exc}", file=sys.stderr)
        return 1

    print("\nValidation Gate Result")
    print("----------------------")
    print(f"Theme ID: {result.theme_id}")
    print(f"Theme Name: {result.theme_name}")
    print(f"Current State: {result.current_state}")
    print(f"Gate Status: {result.gate_status}")
    print(f"Evidence Status: {result.evidence_status}")
    print(f"State Changed: {result.state_changed}")
    print(f"New State: {result.new_state}")
    print(f"Reason: {result.reason}")
    print(f"Recommended Next Action: {result.recommended_next_action}")
    print(f"Policy Version: {result.policy_version}")
    print(f"Run ID: {result.run_id}")
    print(f"Timestamp: {result.timestamp}")

    return 0 if result.gate_status == "READY_FOR_HUMAN_REVIEW" else 1


if __name__ == "__main__":
    raise SystemExit(main())
