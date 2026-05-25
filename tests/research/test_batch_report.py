import pytest

from src.research.batch_report import BatchReportError, PlannedRedditBatchReportGenerator
from src.research.planned_reddit_research_runner import PlannedRedditResearchRunner


def test_batch_report_generator_creates_markdown_report():
    batch_result = PlannedRedditResearchRunner().run_for_industry(
        industry_text="sales",
        limit_per_job=1,
    )

    generator = PlannedRedditBatchReportGenerator()

    report_path = generator.generate(batch_result)

    assert report_path.exists()
    assert report_path.suffix == ".md"

    content = report_path.read_text(encoding="utf-8")

    assert "# Planned Reddit Research Batch Report" in content
    assert "## Batch Summary" in content
    assert "Industry: sales" in content
    assert "## Workflow Cycle" in content
    assert "## Job Results" in content
    assert "## Accountability Notes" in content


def test_batch_report_includes_reports_manifests_and_hermes_memory():
    batch_result = PlannedRedditResearchRunner().run_for_industry(
        industry_text="saas",
        limit_per_job=1,
    )

    report_path = PlannedRedditBatchReportGenerator().generate(batch_result)

    content = report_path.read_text(encoding="utf-8")

    assert "## Generated Opportunity Reports" in content
    assert "## Run Manifests" in content
    assert "## Hermes Memory Records" in content
    assert "reports/opportunities" in content
    assert "reports/intelligence/runs" in content
    assert "data/hermes/research_memory" in content


def test_batch_report_blocks_path_traversal():
    with pytest.raises(BatchReportError):
        PlannedRedditBatchReportGenerator(output_dir="../../unsafe")


def test_batch_report_blocks_output_outside_batches_folder():
    with pytest.raises(BatchReportError):
        PlannedRedditBatchReportGenerator(output_dir="reports/intelligence")
