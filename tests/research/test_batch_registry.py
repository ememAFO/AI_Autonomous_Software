import json

import pytest

from src.research.batch_registry import (
    BatchRegistryError,
    BatchRunRegistryWriter,
)
from src.research.batch_report import PlannedRedditBatchReportGenerator
from src.research.planned_reddit_research_runner import PlannedRedditResearchRunner


def test_batch_registry_adds_batch_to_index():
    batch_result = PlannedRedditResearchRunner().run_for_industry(
        industry_text="sales",
        limit_per_job=1,
    )

    batch_report_path = PlannedRedditBatchReportGenerator(
        output_dir="reports/intelligence/batches/test_reports"
    ).generate(batch_result)

    registry_writer = BatchRunRegistryWriter(
        registry_path="reports/intelligence/test_runs/test_batch_run_index.json"
    )

    registry_path = registry_writer.add_batch(
        batch_result=batch_result,
        batch_report_path=str(batch_report_path),
    )

    assert registry_path.exists()

    data = json.loads(registry_path.read_text(encoding="utf-8"))

    assert "batches" in data
    assert data["batches"]

    latest_batch = data["batches"][-1]

    assert latest_batch["industry"] == "sales"
    assert latest_batch["planned_count"] == batch_result.planned_count
    assert latest_batch["successful_count"] == batch_result.successful_count
    assert latest_batch["blocked_count"] == batch_result.blocked_count
    assert latest_batch["batch_report_path"] == str(batch_report_path)


def test_batch_registry_preserves_existing_batches():
    registry_writer = BatchRunRegistryWriter(
        registry_path="reports/intelligence/test_runs/test_batch_run_index_preserve.json"
    )

    first_batch = PlannedRedditResearchRunner().run_for_industry(
        industry_text="sales",
        limit_per_job=1,
    )

    second_batch = PlannedRedditResearchRunner().run_for_industry(
        industry_text="saas",
        limit_per_job=1,
    )

    registry_writer.add_batch(
        batch_result=first_batch,
        batch_report_path="reports/intelligence/batches/first.md",
    )

    registry_path = registry_writer.add_batch(
        batch_result=second_batch,
        batch_report_path="reports/intelligence/batches/second.md",
    )

    data = json.loads(registry_path.read_text(encoding="utf-8"))

    assert len(data["batches"]) >= 2
    assert data["batches"][-2]["industry"] == "sales"
    assert data["batches"][-1]["industry"] == "saas"


def test_batch_registry_blocks_path_traversal():
    with pytest.raises(BatchRegistryError):
        BatchRunRegistryWriter(registry_path="../../unsafe.json")


def test_batch_registry_blocks_non_json_file():
    with pytest.raises(BatchRegistryError):
        BatchRunRegistryWriter(
            registry_path="reports/intelligence/batch_run_index.txt"
        )
