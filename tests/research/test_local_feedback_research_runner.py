import csv
from pathlib import Path

from src.research.local_feedback_research_runner import LocalFeedbackResearchRunner


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = list(rows[0].keys())

    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def test_local_feedback_research_runner_processes_valid_feedback():
    path = Path("data/raw/external_feedback/test_runner/sales_feedback.csv")

    write_csv(
        path,
        [
            {
                "Content": (
                    "Sales teams lose leads because manual follow up after quotes "
                    "takes too long and customers stop replying."
                ),
                "Date": "2026-05-25",
            }
        ],
    )

    result = LocalFeedbackResearchRunner().run_file(
        path,
        industry="sales",
        source_type="g2_reviews",
        max_rows=1,
    )

    assert result.loaded_count == 1
    assert result.processed_count == 1
    assert result.successful_count == 1
    assert result.blocked_count == 0

    item_result = result.results[0]

    assert item_result.status == "success"
    assert item_result.report_path is not None
    assert item_result.manifest_path is not None
    assert item_result.registry_path is not None
    assert item_result.hermes_memory_path is not None


def test_local_feedback_research_runner_blocks_non_business_feedback():
    path = Path("data/raw/external_feedback/test_runner/non_business.csv")

    write_csv(
        path,
        [
            {
                "Content": "The app colour is nice and I like the font.",
            }
        ],
    )

    result = LocalFeedbackResearchRunner().run_file(
        path,
        industry="saas",
        source_type="app_store_reviews",
        max_rows=1,
    )

    assert result.loaded_count == 1
    assert result.processed_count == 1
    assert result.successful_count == 0
    assert result.blocked_count == 1
    assert result.results[0].status == "blocked"
    assert result.results[0].error is not None


def test_local_feedback_research_runner_respects_max_rows():
    path = Path("data/raw/external_feedback/test_runner/max_rows.csv")

    write_csv(
        path,
        [
            {"Content": "Manual CRM follow up causes lost leads."},
            {"Content": "Manual appointment reminders cause missed bookings."},
        ],
    )

    result = LocalFeedbackResearchRunner().run_file(
        path,
        industry="sales",
        source_type="g2_reviews",
        max_rows=1,
    )

    assert result.loaded_count == 1
    assert result.processed_count == 1

def test_local_feedback_research_runner_extracts_dislike_section_before_pipeline():
    path = Path("data/raw/external_feedback/test_runner/g2_mixed_review.csv")

    write_csv(
        path,
        [
            {
                "Content": (
                    "What do you like best about Example SaaS?"
                    "The dashboard is clean and reporting is useful. "
                    "Review collected by and hosted on G2.com."
                    "What do you dislike about Example SaaS?"
                    "Manual CRM follow up is slow and sales teams lose leads after demos."
                ),
            }
        ],
    )

    result = LocalFeedbackResearchRunner().run_file(
        path,
        industry="sales",
        source_type="g2_reviews",
        max_rows=1,
    )

    assert result.loaded_count == 1
    assert result.processed_count == 1
    assert result.successful_count == 1
    assert result.blocked_count == 0
    assert result.results[0].status == "success"
