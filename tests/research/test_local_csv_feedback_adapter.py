import csv
from pathlib import Path

import pytest

from src.adapters.local_csv_feedback_adapter import (
    LocalCSVFeedbackAdapter,
    LocalCSVFeedbackAdapterError,
)


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = list(rows[0].keys()) if rows else ["Content"]

    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def test_local_csv_feedback_adapter_loads_content_column():
    path = Path("data/raw/external_feedback/test_adapter/content_reviews.csv")
    write_csv(
        path,
        [
            {
                "Content": "Manual CRM follow up is slow and sales teams lose leads.",
                "Date": "2026-05-25",
                "Url": "https://example.com/review",
            }
        ],
    )

    result = LocalCSVFeedbackAdapter().load_file(
        path,
        industry="sales",
        max_rows=10,
    )

    assert result.loaded_count == 1
    assert result.skipped_count == 0
    assert result.text_column == "Content"
    assert result.items[0].text == "Manual CRM follow up is slow and sales teams lose leads."
    assert result.items[0].industry == "sales"
    assert result.items[0].source_type == "local_csv_feedback"
    assert result.items[0].metadata["Date"] == "2026-05-25"


def test_local_csv_feedback_adapter_loads_reviews_column():
    path = Path("data/raw/external_feedback/test_adapter/reviews.csv")
    write_csv(
        path,
        [
            {
                "Reviews": "Customers complain that appointment reminders are poor.",
            }
        ],
    )

    result = LocalCSVFeedbackAdapter().load_file(
        path,
        industry="customer support",
        max_rows=10,
    )

    assert result.loaded_count == 1
    assert result.text_column == "Reviews"
    assert "appointment reminders" in result.items[0].text


def test_local_csv_feedback_adapter_skips_blank_text_rows():
    path = Path("data/raw/external_feedback/test_adapter/blank_rows.csv")
    write_csv(
        path,
        [
            {"Content": ""},
            {"Content": "Support replies are slow and customers churn."},
        ],
    )

    result = LocalCSVFeedbackAdapter().load_file(
        path,
        industry="customer support",
        max_rows=10,
    )

    assert result.loaded_count == 1
    assert result.skipped_count == 1


def test_local_csv_feedback_adapter_respects_max_rows():
    path = Path("data/raw/external_feedback/test_adapter/max_rows.csv")
    write_csv(
        path,
        [
            {"Content": "First complaint about missing integrations."},
            {"Content": "Second complaint about missing integrations."},
        ],
    )

    result = LocalCSVFeedbackAdapter().load_file(
        path,
        industry="saas",
        max_rows=1,
    )

    assert result.loaded_count == 1


def test_local_csv_feedback_adapter_blocks_path_traversal():
    with pytest.raises(LocalCSVFeedbackAdapterError):
        LocalCSVFeedbackAdapter().load_file(
            "../../unsafe.csv",
            industry="sales",
        )


def test_local_csv_feedback_adapter_blocks_non_csv_file():
    path = Path("data/raw/external_feedback/test_adapter/not_csv.txt")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("not csv", encoding="utf-8")

    with pytest.raises(LocalCSVFeedbackAdapterError):
        LocalCSVFeedbackAdapter().load_file(
            path,
            industry="sales",
        )


def test_local_csv_feedback_adapter_blocks_empty_industry():
    path = Path("data/raw/external_feedback/test_adapter/empty_industry.csv")
    write_csv(path, [{"Content": "Some useful feedback."}])

    with pytest.raises(LocalCSVFeedbackAdapterError):
        LocalCSVFeedbackAdapter().load_file(
            path,
            industry="",
        )


def test_local_csv_feedback_adapter_blocks_excessive_max_rows():
    path = Path("data/raw/external_feedback/test_adapter/excessive.csv")
    write_csv(path, [{"Content": "Some useful feedback."}])

    with pytest.raises(LocalCSVFeedbackAdapterError):
        LocalCSVFeedbackAdapter().load_file(
            path,
            industry="sales",
            max_rows=1000,
        )


def test_local_csv_feedback_adapter_blocks_missing_text_column():
    path = Path("data/raw/external_feedback/test_adapter/no_text_column.csv")
    write_csv(path, [{"OnlyDate": "2026-05-25"}])

    with pytest.raises(LocalCSVFeedbackAdapterError):
        LocalCSVFeedbackAdapter().load_file(
            path,
            industry="sales",
        )
