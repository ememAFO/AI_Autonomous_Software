import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.research.weekly_report import (
    WeeklyIntelligenceReportError,
    WeeklyIntelligenceReportGenerator,
)
from src.utils.audit_logger import AuditEvent, AuditLogger


def main() -> int:
    try:
        generator = WeeklyIntelligenceReportGenerator()
        report_path = generator.generate()

        AuditLogger().log(
            AuditEvent(
                action="weekly_intelligence_report",
                status="success",
                details={
                    "report_path": str(report_path),
                },
            )
        )

        print("\nWeekly Intelligence Report Generated")
        print("------------------------------------")
        print(f"- {report_path}")

        return 0

    except WeeklyIntelligenceReportError as exc:
        AuditLogger().log(
            AuditEvent(
                action="weekly_intelligence_report",
                status="blocked",
                details={
                    "error": str(exc),
                },
            )
        )

        print(f"Weekly report blocked: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
