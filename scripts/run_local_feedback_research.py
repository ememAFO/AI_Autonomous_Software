import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.adapters.local_csv_feedback_adapter import LocalCSVFeedbackAdapterError
from src.research.local_feedback_research_runner import LocalFeedbackResearchRunner
from src.utils.audit_logger import AuditEvent, AuditLogger


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run local CSV feedback through the research pipeline."
    )

    parser.add_argument(
        "--file",
        required=True,
        help="CSV file path inside data/raw/external_feedback.",
    )

    parser.add_argument(
        "--industry",
        required=True,
        help="Industry label for this dataset. Example: saas, sales, customer support",
    )

    parser.add_argument(
        "--source-type",
        default="local_csv_feedback",
        help="Source type label. Example: g2_reviews, trustpilot_reviews, app_store_reviews",
    )

    parser.add_argument(
        "--max-rows",
        type=int,
        default=10,
        help="Maximum rows to process.",
    )

    return parser.parse_args()


def main() -> int:
    args = parse_args()

    try:
        runner = LocalFeedbackResearchRunner()

        result = runner.run_file(
            args.file,
            industry=args.industry,
            source_type=args.source_type,
            max_rows=args.max_rows,
        )

        AuditLogger().log(
            AuditEvent(
                action="local_feedback_research",
                status="success",
                details={
                    "source_path": result.source_path,
                    "industry": result.industry,
                    "source_type": result.source_type,
                    "loaded_count": result.loaded_count,
                    "processed_count": result.processed_count,
                    "successful_count": result.successful_count,
                    "blocked_count": result.blocked_count,
                    "results": [
                        {
                            "status": item_result.status,
                            "report_path": item_result.report_path,
                            "manifest_path": item_result.manifest_path,
                            "registry_path": item_result.registry_path,
                            "hermes_memory_path": item_result.hermes_memory_path,
                            "error": item_result.error,
                        }
                        for item_result in result.results
                    ],
                },
            )
        )

        print("\nLocal Feedback Research Complete")
        print("--------------------------------")
        print(f"Source Path: {result.source_path}")
        print(f"Industry: {result.industry}")
        print(f"Source Type: {result.source_type}")
        print(f"Loaded Rows: {result.loaded_count}")
        print(f"Processed Rows: {result.processed_count}")
        print(f"Successful Rows: {result.successful_count}")
        print(f"Blocked Rows: {result.blocked_count}")

        print("\nItem Results:")
        for index, item_result in enumerate(result.results, start=1):
            print(
                f"{index}. {item_result.status.upper()} | "
                f"report={item_result.report_path or 'N/A'} | "
                f"manifest={item_result.manifest_path or 'N/A'}"
            )

            if item_result.error:
                print(f"   Error: {item_result.error}")

        return 0

    except LocalCSVFeedbackAdapterError as exc:
        AuditLogger().log(
            AuditEvent(
                action="local_feedback_research",
                status="blocked",
                details={
                    "file": args.file,
                    "industry": args.industry,
                    "source_type": args.source_type,
                    "error": str(exc),
                },
            )
        )

        print(f"Local feedback research blocked: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
