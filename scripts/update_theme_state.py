import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.hermes.theme_state_registry import (
    ThemeStateRegistry,
    ThemeStateRegistryError,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Register or transition a theme in the Theme State Registry."
    )

    parser.add_argument(
        "--action",
        required=True,
        choices=["register", "transition", "current-state", "history"],
        help="State registry action to perform.",
    )

    parser.add_argument("--theme-id", required=True)
    parser.add_argument("--theme-name", required=True)

    parser.add_argument(
        "--new-state",
        default=None,
        help="New state for transition action.",
    )

    parser.add_argument(
        "--trigger",
        default="manual_state_update",
        help="What triggered the state change.",
    )

    parser.add_argument(
        "--reason",
        default="Manual state update.",
        help="Reason for the state change.",
    )

    parser.add_argument(
        "--changed-by",
        default="update_theme_state_cli",
        help="Actor or component responsible for the change.",
    )

    parser.add_argument(
        "--related-artifact-id",
        default="manual_cli_update",
        help="Related artifact ID or reference.",
    )

    parser.add_argument(
        "--policy-version",
        default="2026-06-08.v1",
        help="Policy version used for the state change.",
    )

    parser.add_argument(
        "--run-id",
        default="manual_cli_run",
        help="Run ID for traceability.",
    )

    parser.add_argument(
        "--registry-path",
        default="reports/intelligence/theme_state_registry.json",
        help="Path to the theme state registry JSON file.",
    )

    return parser.parse_args()


def main() -> int:
    args = parse_args()
    registry = ThemeStateRegistry(registry_path=args.registry_path)

    try:
        if args.action == "register":
            event = registry.register_theme(
                theme_id=args.theme_id,
                theme_name=args.theme_name,
                trigger=args.trigger,
                reason=args.reason,
                changed_by=args.changed_by,
                related_artifact_id=args.related_artifact_id,
                policy_version=args.policy_version,
                run_id=args.run_id,
            )

            print("\nTheme Registered")
            print("----------------")
            print(f"Theme ID: {event.theme_id}")
            print(f"Theme Name: {event.theme_name}")
            print(f"State: {event.new_state}")
            print(f"Event ID: {event.event_id}")
            print(f"Timestamp: {event.timestamp}")
            return 0

        if args.action == "transition":
            if not args.new_state:
                print("--new-state is required for transition action", file=sys.stderr)
                return 1

            event = registry.transition(
                theme_id=args.theme_id,
                theme_name=args.theme_name,
                new_state=args.new_state,
                trigger=args.trigger,
                reason=args.reason,
                changed_by=args.changed_by,
                related_artifact_id=args.related_artifact_id,
                policy_version=args.policy_version,
                run_id=args.run_id,
            )

            print("\nTheme State Updated")
            print("-------------------")
            print(f"Theme ID: {event.theme_id}")
            print(f"Theme Name: {event.theme_name}")
            print(f"Previous State: {event.previous_state}")
            print(f"New State: {event.new_state}")
            print(f"Event ID: {event.event_id}")
            print(f"Timestamp: {event.timestamp}")
            return 0

        if args.action == "current-state":
            current_state = registry.get_current_state(args.theme_id)

            print("\nCurrent Theme State")
            print("-------------------")
            print(f"Theme ID: {args.theme_id}")
            print(f"Theme Name: {args.theme_name}")
            print(f"Current State: {current_state or 'NOT_REGISTERED'}")
            return 0

        if args.action == "history":
            events = registry.list_events_for_theme(args.theme_id)

            print("\nTheme State History")
            print("-------------------")
            print(f"Theme ID: {args.theme_id}")
            print(f"Theme Name: {args.theme_name}")

            if not events:
                print("No state events found.")
                return 0

            for event in events:
                print("")
                print(f"- Event ID: {event.event_id}")
                print(f"  Previous State: {event.previous_state}")
                print(f"  New State: {event.new_state}")
                print(f"  Trigger: {event.trigger}")
                print(f"  Changed By: {event.changed_by}")
                print(f"  Reason: {event.reason}")
                print(f"  Timestamp: {event.timestamp}")

            return 0

    except ThemeStateRegistryError as exc:
        print(f"Theme state update blocked: {exc}", file=sys.stderr)
        return 1

    print(f"Unsupported action: {args.action}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
