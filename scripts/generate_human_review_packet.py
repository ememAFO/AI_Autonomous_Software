import argparse
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


from src.hermes.human_review_packet import (
    HumanReviewPacketError,
    HumanReviewPacketGenerator,
    HumanReviewPacketRegistry,
    HumanReviewPacketRegistryError,
)
from src.hermes.theme_state_registry import ThemeStateRegistry
from src.hermes.theme_validation_plan_registry import (
    ThemeValidationPlanRegistry,
)
from src.hermes.validation_evidence_log import ValidationEvidenceLog


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Generate a read-only human review packet for a theme that has "
            "already passed the validation gate."
        )
    )

    parser.add_argument("--theme-id", required=True)
    parser.add_argument("--theme-name", required=True)

    parser.add_argument(
        "--policy-version",
        default="2026-06-08.v1",
    )

    parser.add_argument(
        "--run-id",
        default="manual_human_review_packet",
    )

    parser.add_argument(
        "--state-registry-path",
        default="reports/intelligence/theme_state_registry.json",
    )

    parser.add_argument(
        "--plan-registry-path",
        default="reports/intelligence/validation_plan_index.json",
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
        "--output-path",
        default=None,
        help=(
            "Optional Markdown output path inside "
            "reports/intelligence/human_review_packets."
        ),
    )

    return parser.parse_args()


def main() -> int:
    args = parse_args()

    generator = HumanReviewPacketGenerator(
        state_registry=ThemeStateRegistry(
            registry_path=args.state_registry_path,
        ),
        validation_plan_registry=ThemeValidationPlanRegistry(
            registry_path=args.plan_registry_path,
        ),
        evidence_log=ValidationEvidenceLog(
            log_path=args.evidence_log_path,
        ),
    )

    packet_registry = HumanReviewPacketRegistry(
        registry_path=args.packet_registry_path,
    )

    written_path = None

    try:
        packet = generator.generate(
            theme_id=args.theme_id,
            theme_name=args.theme_name,
            policy_version=args.policy_version,
            run_id=args.run_id,
        )

        output_path = (
            Path(args.output_path)
            if args.output_path
            else generator.default_output_path(packet)
        )

        written_path = generator.write_markdown(
            packet=packet,
            output_path=output_path,
        )

        try:
            registry_entry = packet_registry.add_packet(
                packet=packet,
                output_path=written_path,
            )
        except HumanReviewPacketRegistryError:
            if written_path.exists():
                written_path.unlink()

            raise

    except (
        HumanReviewPacketError,
        HumanReviewPacketRegistryError,
    ) as exc:
        print(f"Human review packet blocked: {exc}", file=sys.stderr)
        return 1

    print("\nHuman Review Packet Generated")
    print("-----------------------------")
    print(f"Packet ID: {packet.packet_id}")
    print(f"Theme ID: {packet.theme_id}")
    print(f"Theme Name: {packet.theme_name}")
    print(f"Current State: {packet.current_state}")
    print(f"Review Status: {packet.review_status}")
    print(f"Evidence Status: {packet.evidence_summary.status}")
    print(
        "Gate-Safe Evidence: "
        f"{packet.evidence_summary.gate_safe_entries}"
    )
    print(
        "Excluded / Suspect Evidence: "
        f"{packet.evidence_summary.suspect_entries}"
    )
    print(f"Validation Plan: {packet.validation_plan_path}")
    print(f"Output Path: {written_path}")
    print(f"Packet Registry Timestamp: {registry_entry.timestamp}")
    print(
        "Governance: packet generation does not approve building or "
        "change state."
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
