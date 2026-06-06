import csv
from pathlib import Path

import pytest

from src.research.local_dataset_profiler import (
    LocalDatasetProfiler,
    LocalDatasetProfilerError,
)


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def test_local_dataset_profiler_profiles_g2_style_dataset():
    path = Path("data/raw/external_feedback/test_profiler/g2_sample.csv")

    write_csv(
        path,
        [
            {
                "product_name": "Zapier",
                "vendor_name": "Zapier",
                "stars": "3",
                "date": "2026-01-01",
                "title": "Hard to configure",
                "text": "Some Zaps are difficult to configure and integrations break.",
            }
        ],
    )

    profile = LocalDatasetProfiler().profile(path)

    assert profile.row_count == 1
    assert profile.detected_text_column == "text"
    assert profile.detected_rating_column == "stars"
    assert profile.detected_date_column == "date"
    assert profile.detected_product_column == "product_name"
    assert profile.detected_vendor_column == "vendor_name"
    assert profile.suggested_source_type == "g2_reviews"
    assert profile.suggested_industry == "saas"
    assert profile.suggested_source_quality == "core_evidence"


def test_local_dataset_profiler_detects_missing_text_column():
    path = Path("data/raw/external_feedback/test_profiler/no_text.csv")

    write_csv(
        path,
        [
            {
                "product_name": "Example",
                "stars": "5",
            }
        ],
    )

    profile = LocalDatasetProfiler().profile(path)

    assert profile.detected_text_column is None
    assert "No text column detected. Adapter may need updating before ingestion." in profile.notes


def test_local_dataset_profiler_recommends_small_first_run_for_large_dataset():
    path = Path("data/raw/external_feedback/test_profiler/large.csv")

    rows = [
        {
            "text": f"Review {index}",
            "stars": "3",
        }
        for index in range(150)
    ]

    write_csv(path, rows)

    profile = LocalDatasetProfiler().profile(path)

    assert profile.row_count == 150
    assert profile.recommended_first_run_rows == 50


def test_local_dataset_profiler_blocks_missing_file():
    with pytest.raises(LocalDatasetProfilerError):
        LocalDatasetProfiler().profile("data/raw/external_feedback/test_profiler/missing.csv")


def test_local_dataset_profiler_blocks_non_csv_file():
    path = Path("data/raw/external_feedback/test_profiler/readme.txt")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("not csv", encoding="utf-8")

    with pytest.raises(LocalDatasetProfilerError):
        LocalDatasetProfiler().profile(path)
