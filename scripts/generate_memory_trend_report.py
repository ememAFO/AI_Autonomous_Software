import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.hermes.memory_trend_detector import (
    HermesMemoryTrendDetector,
    MemoryTrendDetectorError,
)
from src.hermes.memory_trend_report import (
    HermesMemoryTrendReportGenerator,
    MemoryTrendReportError,
)
from src.utils.audit_logger import AuditEvent, AuditLogger


def main() -> int:
    try:
        summary = HermesMemoryTrendDetector().summarize()
        report_path = HermesMemoryTrendReportGenerator().generate(summary)

        AuditLogger().log(
            AuditEvent(
                action="hermes_memory_trend_report",
                status="success",
                details={
                    "report_path": str(report_path),
                    "total_records": summary.total_records,
                    "high_confidence_records": len(summary.high_confidence_records),
                },
            )
        )

        print("\nHermes Memory Trend Report Generated")
        print("------------------------------------")
        print(f"- {report_path}")

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
