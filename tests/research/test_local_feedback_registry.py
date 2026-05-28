import csv
import json
from pathlib import Path

import pytest

from src.research.local_feedback_registry import (
    LocalFeedbackRegistryError,
    LocalFeedbackRunRegistryWriter,
)
from src.research.local_feedback_report import LocalFeedbackReportGenerator
from src.research.local_feedback_research_runner import LocalFeedbackResearchRunner


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = list(rows[0].keys())

    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def test_local_feedback_registry_adds_run_to_index():
    path = Path("data/raw/external_feedback/test_local_feedback_registry/feedback.csv")

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
        output_dir="reports/intelligence/local_feedback/test_registry_reports"
    ).generate(run_result)

    registry_writer = LocalFeedbackRunRegistryWriter(
        registry_path="reports/intelligence/test_runs/test_local_feedback_run_index.json"
    )

    registry_path = registry_writer.add_run(
        run_result=run_result,
        local_feedback_report_path=str(report_path),
    )

    assert registry_path.exists()

    data = json.loads(registry_path.read_text(encoding="utf-8"))

    assert "runs" in data
    assert data["runs"]

    latest_run = data["runs"][-1]

    assert latest_run["industry"] == "sales"
    assert latest_run["source_type"] == "g2_reviews"
    assert latest_run["loaded_count"] == run_result.loaded_count
    assert latest_run["processed_count"] == run_result.processed_count
    assert latest_run["successful_count"] == run_result.successful_count
    assert latest_run["blocked_count"] == run_result.blocked_count
    assert latest_run["local_feedback_report_path"] == str(report_path)


def test_local_feedback_registry_preserves_existing_runs():
    registry_writer = LocalFeedbackRunRegistryWriter(
        registry_path="reports/intelligence/test_runs/test_local_feedback_run_index_preserve.json"
    )

    first_path = Path("data/raw/external_feedback/test_local_feedback_registry/first.csv")
    second_path = Path("data/raw/external_feedback/test_local_feedback_registry/second.csv")

    write_csv(
        first_path,
        [{"Content": "Manual CRM follow up causes lost leads."}],
    )

    write_csv(
        second_path,
        [{"Content": "The integration creates duplicate contacts and is difficult to resolve."}],
    )

    first_result = LocalFeedbackResearchRunner().run_file(
        first_path,
        industry="sales",
        source_type="g2_reviews",
        max_rows=1,
    )

    second_result = LocalFeedbackResearchRunner().run_file(
        second_path,
        industry="saas",
        source_type="g2_reviews",
        max_rows=1,
    )

    registry_writer.add_run(
        run_result=first_result,
        local_feedback_report_path="reports/intelligence/local_feedback/first.md",
    )

    registry_path = registry_writer.add_run(
        run_result=second_result,
        local_feedback_report_path="reports/intelligence/local_feedback/second.md",
    )

    data = json.loads(registry_path.read_text(encoding="utf-8"))

    assert len(data["runs"]) >= 2
    assert data["runs"][-2]["industry"] == "sales"
    assert data["runs"][-1]["industry"] == "saas"


def test_local_feedback_registry_blocks_path_traversal():
    with pytest.raises(LocalFeedbackRegistryError):
        LocalFeedbackRunRegistryWriter(registry_path="../../unsafe.json")


def test_local_feedback_registry_blocks_non_json_file():
    with pytest.raises(LocalFeedbackRegistryError):
        LocalFeedbackRunRegistryWriter(
            registry_path="reports/intelligence/local_feedback_run_index.txt"
        )
