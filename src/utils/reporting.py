from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path


REPORT_TEMPLATE = """# {title}

Generated: {generated_at}

## Summary
{summary}

## Risks
{risks}

## Failed Checks
{failed_checks}

## Next Actions
{next_actions}
"""


class ReportWriter:
    def __init__(self, reports_root: Path | str = "reports") -> None:
        self.reports_root = Path(reports_root)

    def write_report(
        self,
        category: str,
        filename: str,
        title: str,
        summary: str,
        risks: list[str] | None = None,
        failed_checks: list[str] | None = None,
        next_actions: list[str] | None = None,
    ) -> Path:
        folder = self.reports_root / category
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / filename
        path.write_text(
            REPORT_TEMPLATE.format(
                title=title,
                generated_at=datetime.now(timezone.utc).isoformat(),
                summary=summary,
                risks="\n".join(f"- {item}" for item in (risks or ["None identified."])),
                failed_checks="\n".join(f"- {item}" for item in (failed_checks or ["None."])),
                next_actions="\n".join(f"- {item}" for item in (next_actions or ["Continue to next approved stage."])),
            ),
            encoding="utf-8",
        )
        return path
