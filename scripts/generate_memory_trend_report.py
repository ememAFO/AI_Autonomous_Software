import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.hermes.memory_trend_detector import (
    HermesMemoryTrendDetector,
    MemoryTrendDetectorError,
    MemoryTrendFilter,
)
from src.hermes.memory_trend_report import (
    HermesMemoryTrendReportGenerator,
    MemoryTrendReportError,
)
from src.utils.audit_logger import AuditEvent, AuditLogger
from src.utils.label_normalizer import LabelNormalizer


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate a Hermes memory trend report."
    )

    parser.add_argument(
        "--industry",
        help="Optional industry filter. Example: saas, sales, airline",
    )

    parser.add_argument(
        "--source",
        help="Optional source filter. Example: reddit, review_site",
    )

    parser.add_argument(
        "--exclude-source",
        help="Optional source exclusion filter. Example: reddit",
    )

    parser.add_argument(
        "--recommendation",
        help="Optional recommendation filter. Example: BUILD_NOW, VALIDATE_FIRST",
    )

    return parser.parse_args()


def main() -> int:
    args = parse_args()
    normalizer = LabelNormalizer()

    filters = MemoryTrendFilter(
        industry=normalizer.normalize(args.industry) if args.industry else None,
        source=normalizer.normalize(args.source) if args.source else None,
        exclude_source=normalizer.normalize(args.exclude_source) if args.exclude_source else None,
        recommendation=args.recommendation.upper() if args.recommendation else None,
    )

    try:
        summary = HermesMemoryTrendDetector().summarize(filters=filters)
        report_path = HermesMemoryTrendReportGenerator().generate(summary)

        AuditLogger().log(
            AuditEvent(
                action="hermes_memory_trend_report",
                status="success",
                details={
                    "report_path": str(report_path),
                    "total_records": summary.total_records,
                    "filtered_records": summary.filtered_records,
                    "high_confidence_records": len(summary.high_confidence_records),
                    "filters": {
                        "industry": filters.industry,
                        "source": filters.source,
                        "exclude_source": filters.exclude_source,
                        "recommendation": filters.recommendation,
                    },
                },
            )
        )

        print("\nHermes Memory Trend Report Generated")
        print("------------------------------------")
        print(f"- {report_path}")
        print(f"Total Records: {summary.total_records}")
        print(f"Filtered Records: {summary.filtered_records}")

        return 0

    except (MemoryTrendDetectorError, MemoryTrendReportError) as exc:
        AuditLogger().log(
            AuditEvent(
                action="hermes_memory_trend_report",
                status="blocked",
                details={
                    "error": str(exc),
                },
            )
        )

        print(f"Hermes memory trend report blocked: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
