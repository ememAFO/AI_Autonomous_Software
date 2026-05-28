import csv
from pathlib import Path

import pytest

from src.research.local_feedback_report import (
    LocalFeedbackReportError,
    LocalFeedbackReportGenerator,
)
from src.research.local_feedback_research_runner import LocalFeedbackResearchRunner


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = list(rows[0].keys())

    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def test_local_feedback_report_generator_creates_report():
    path = Path("data/raw/external_feedback/test_local_feedback_report/feedback.csv")

    write_csv(
        path,
        [
            {
                "Content": (
                    "Sales teams lose leads because manual follow up after quotes "
                    "takes too long and customers stop replying."
                )
            }
        ],
    )

    run_result = LocalFeedbackResearchRunner().run_file(
        path,
        industry="sales",
        source_type="g2_reviews",
        max_rows=1,
    )

    report_path = LocalFeedbackReportGenerator(
        output_dir="reports/intelligence/local_feedback/test_reports"
    ).generate(run_result)

    assert report_path.exists()
    assert report_path.suffix == ".md"

    content = report_path.read_text(encoding="utf-8")

    assert "# Local Feedback Research Report" in content
    assert "## Run Summary" in content
    assert "## Workflow Cycle" in content
    assert "## Item Results" in content
    assert "## Accountability Notes" in content
    assert "Successful Rows: 1" in content
    assert "- - Row" not in content

def test_local_feedback_report_includes_blocked_rows():
    path = Path("data/raw/external_feedback/test_local_feedback_report/blocked.csv")

    write_csv(
        path,
        [
            {
                "Content": "The colour is nice and I like the font."
            }
        ],
    )

    run_result = LocalFeedbackResearchRunner().run_file(
        path,
        industry="saas",
        source_type="app_store_reviews",
        max_rows=1,
    )

    report_path = LocalFeedbackReportGenerator(
        output_dir="reports/intelligence/local_feedback/test_reports"
    ).generate(run_result)

    content = report_path.read_text(encoding="utf-8")

    assert "Blocked Rows: 1" in content
    assert "## Blocked Row Errors" in content
    assert "No valid business pain detected" in content


def test_local_feedback_report_blocks_path_traversal():
    with pytest.raises(LocalFeedbackReportError):
        LocalFeedbackReportGenerator(output_dir="../../unsafe")


def test_local_feedback_report_blocks_output_outside_local_feedback_folder():
    with pytest.raises(LocalFeedbackReportError):
        LocalFeedbackReportGenerator(output_dir="reports/intelligence")
