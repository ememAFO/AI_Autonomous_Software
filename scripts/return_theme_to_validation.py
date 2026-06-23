import argparse
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


from src.hermes.human_review_decision import (
    HumanReviewDecisionError,
    HumanReviewDecisionService,
)
from src.hermes.theme_state_registry import ThemeStateRegistry
from src.hermes.validation_evidence_log import ValidationEvidenceLog
from src.hermes.validation_evidence_summary import (
    ValidationEvidenceSummarizer,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Record a human decision to return a review-ready theme to "
            "validation after evidence repair is required."
        )
    )

    parser.add_argument("--theme-id", required=True)
    parser.add_argument("--theme-name", required=True)

    parser.add_argument(
        "--reviewer-reference",
        required=True,
        help=(
            "Anonymous reviewer reference only. Do not use a customer name, "
            "email address, phone number, or other personal data."
        ),
    )

    parser.add_argument(
        "--decision-reason",
        required=True,
    )

    parser.add_argument(
        "--review-context-path",
        required=True,
        help=(
            "Existing Markdown evidence-repair context inside "
            "reports/intelligence."
        ),
    )

    parser.add_argument(
        "--policy-version",
        default="2026-06-08.v1",
    )

    parser.add_argument(
        "--run-id",
        default="manual_human_review_return",
    )

    parser.add_argument(
        "--state-registry-path",
        default="reports/intelligence/theme_state_registry.json",
    )

    parser.add_argument(
        "--evidence-log-path",
        default="reports/intelligence/validation_evidence_log.json",
    )

    return parser.parse_args()


def main() -> int:
    args = parse_args()

    service = HumanReviewDecisionService(
        state_registry=ThemeStateRegistry(
            registry_path=args.state_registry_path,
        ),
        evidence_summarizer=ValidationEvidenceSummarizer(
            ValidationEvidenceLog(
                log_path=args.evidence_log_path,
            )
        ),
    )

    try:
        result = service.return_to_validation(
            theme_id=args.theme_id,
            theme_name=args.theme_name,
            reviewer_reference=args.reviewer_reference,
            decision_reason=args.decision_reason,
            review_context_path=args.review_context_path,
            policy_version=args.policy_version,
            run_id=args.run_id,
        )
    except HumanReviewDecisionError as exc:
        print(
            f"Human review return blocked: {exc}",
            file=sys.stderr,
        )
        return 1

    print("\nHuman Review Return Recorded")
    print("----------------------------")
    print(f"Theme ID: {result.theme_id}")
    print(f"Theme Name: {result.theme_name}")
    print(f"Previous State: {result.previous_state}")
    print(f"New State: {result.new_state}")
    print(f"Decision Status: {result.decision_status}")
    print(f"Evidence Status: {result.evidence_status}")
    print(f"Reviewer Reference: {result.reviewer_reference}")
    print(f"Review Context: {result.review_context_path}")
    print(f"State Event ID: {result.state_event_id}")
    print(f"Policy Version: {result.policy_version}")
    print(f"Run ID: {result.run_id}")
    print(f"Timestamp: {result.timestamp}")
    print(f"Recommended Next Action: {result.recommended_next_action}")
    print(
        "Governance: this returns the theme to validation only; "
        "it does not approve MVP planning."
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
