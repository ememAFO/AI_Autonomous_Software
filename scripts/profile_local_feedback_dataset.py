import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.research.local_dataset_profiler import (
    LocalDatasetProfiler,
    LocalDatasetProfilerError,
)
from src.utils.audit_logger import AuditEvent, AuditLogger


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Profile a local CSV feedback dataset before ingestion."
    )

    parser.add_argument(
        "--file",
        required=True,
        help="Path to the local CSV dataset.",
    )

    return parser.parse_args()


def main() -> int:
    args = parse_args()

    try:
        profile = LocalDatasetProfiler().profile(args.file)

        AuditLogger().log(
            AuditEvent(
                action="profile_local_feedback_dataset",
                status="success",
                details={
                    "source_path": profile.source_path,
                    "row_count": profile.row_count,
                    "detected_text_column": profile.detected_text_column,
                    "suggested_source_type": profile.suggested_source_type,
                    "suggested_industry": profile.suggested_industry,
                    "suggested_source_quality": profile.suggested_source_quality,
                },
            )
        )

        print("\nLocal Feedback Dataset Profile")
        print("------------------------------")
        print(f"Source Path: {profile.source_path}")
        print(f"Rows: {profile.row_count}")
        print(f"Columns: {', '.join(profile.columns)}")
        print(f"Text Column: {profile.detected_text_column or 'N/A'}")
        print(f"Rating Column: {profile.detected_rating_column or 'N/A'}")
        print(f"Date Column: {profile.detected_date_column or 'N/A'}")
        print(f"Product Column: {profile.detected_product_column or 'N/A'}")
        print(f"Vendor Column: {profile.detected_vendor_column or 'N/A'}")
        print(f"Empty Text Rows: {profile.empty_text_rows}")
        print(f"Suggested Industry: {profile.suggested_industry}")
        print(f"Suggested Source Type: {profile.suggested_source_type}")
        print(f"Suggested Source Quality: {profile.suggested_source_quality}")
        print(f"Recommended First Run Rows: {profile.recommended_first_run_rows}")

        if profile.sample_text_preview:
            print("\nSample Text Preview:")
            print(profile.sample_text_preview)

        print("\nNotes:")
        for note in profile.notes:
            print(f"- {note}")

        return 0

    except LocalDatasetProfilerError as exc:
        AuditLogger().log(
            AuditEvent(
                action="profile_local_feedback_dataset",
                status="blocked",
                details={
                    "error": str(exc),
                    "source_path": args.file,
                },
            )
        )

        print(f"Dataset profiling blocked: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
