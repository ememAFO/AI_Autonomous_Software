import argparse
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


from src.hermes.human_review_decision import (
    HumanReviewDecisionError,
    HumanReviewResolutionService,
)
from src.hermes.human_review_packet import (
    HumanReviewPacketRegistry,
    HumanReviewPacketRegistryError,
)
from src.hermes.theme_state_registry import (
    ThemeStateRegistry,
    ThemeStateRegistryError,
)
from src.hermes.validation_evidence_log import (
    ValidationEvidenceLog,
    ValidationEvidenceLogError,
)
from src.hermes.validation_evidence_summary import (
    ValidationEvidenceSummarizer,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Record a final human-review decision for a registered human "
            "review packet. This does not approve implementation or deployment."
        )
    )

    parser.add_argument("--theme-id", required=True)
    parser.add_argument("--theme-name", required=True)
    parser.add_argument(
        "--decision",
        required=True,
        choices=["approve_mvp_planning", "reject"],
        help=(
            "approve_mvp_planning moves only to MVP_PLANNING; reject moves "
            "to REJECTED."
        ),
    )
    parser.add_argument("--reviewer-reference", required=True)
    parser.add_argument("--decision-reason", required=True)
    parser.add_argument("--review-packet-id", required=True)
    parser.add_argument("--policy-version", default="2026-06-08.v1")
    parser.add_argument("--run-id", default="manual_human_review_resolution")
    parser.add_argument(
        "--state-registry-path",
        default="reports/intelligence/theme_state_registry.json",
    )
    parser.add_argument(
        "--evidence-log-path",
        default="reports/intelligence/validation_evidence_log.json",
    )
    parser.add_argument(
        "--packet-registry-path",
        default="reports/intelligence/human_review_packet_index.json",
    )
    parser.add_argument(
        "--packet-output-dir",
        default="reports/intelligence/human_review_packets",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    try:
        evidence_log = ValidationEvidenceLog(
            log_path=args.evidence_log_path,
        )
        service = HumanReviewResolutionService(
            state_registry=ThemeStateRegistry(
                registry_path=args.state_registry_path,
            ),
            evidence_summarizer=ValidationEvidenceSummarizer(evidence_log),
            packet_registry=HumanReviewPacketRegistry(
                registry_path=args.packet_registry_path,
                packet_output_dir=args.packet_output_dir,
            ),
        )
        result = service.resolve(
            theme_id=args.theme_id,
            theme_name=args.theme_name,
            decision=args.decision,
            reviewer_reference=args.reviewer_reference,
            decision_reason=args.decision_reason,
            review_packet_id=args.review_packet_id,
            policy_version=args.policy_version,
            run_id=args.run_id,
        )
    except (
        HumanReviewDecisionError,
        HumanReviewPacketRegistryError,
        ThemeStateRegistryError,
        ValidationEvidenceLogError,
    ) as exc:
        print(f"Human review resolution blocked: {exc}", file=sys.stderr)
        return 1

    print("\nHuman Review Resolution Recorded")
    print("--------------------------------")
    print(f"Theme ID: {result.theme_id}")
    print(f"Theme Name: {result.theme_name}")
    print(f"Decision: {result.decision}")
    print(f"Previous State: {result.previous_state}")
    print(f"New State: {result.new_state}")
    print(f"Reviewer Reference: {result.reviewer_reference}")
    print(f"Review Packet ID: {result.review_packet_id}")
    print(f"Review Packet: {result.review_packet_path}")
    print(f"State Event ID: {result.state_event_id}")
    print(f"Policy Version: {result.policy_version}")
    print(f"Run ID: {result.run_id}")
    print(f"Timestamp: {result.timestamp}")
    print(f"Recommended Next Action: {result.recommended_next_action}")
    print(
        "Governance: MVP_PLANNING is planning only; this command does not "
        "approve implementation, integration, deployment, or autonomous execution."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
