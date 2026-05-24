import json

import pytest

from src.research.weekly_report import (
    WeeklyIntelligenceReportError,
    WeeklyIntelligenceReportGenerator,
)


def test_weekly_report_generator_creates_markdown_report():
    generator = WeeklyIntelligenceReportGenerator()

    report_path = generator.generate()

    assert report_path.exists()
    assert report_path.name == "weekly_intelligence_report.md"

    content = report_path.read_text(encoding="utf-8")

    assert "# Weekly Research Intelligence Report" in content
    assert "## Summary" in content
    assert "## Recommended Next Actions" in content


def test_weekly_report_generator_summarizes_registry_data():
    registry_path = "reports/intelligence/test_weekly_registry.json"

    registry_data = {
        "runs": [
            {
                "run_id": "run-1",
                "status": "success",
                "query": "manual follow up",
                "subreddit": "smallbusiness",
                "industry": "home services",
                "final_workflow_stage": "REPORT",
                "processed_count": 2,
                "accepted_count": 2,
                "rejected_count": 0,
                "manifest_path": "reports/intelligence/runs/run-1.json",
                "report_paths": [
                    "reports/opportunities/lead_follow-up_automation.md"
                ],
                "timestamp": "2026-05-23T20:00:00+00:00",
            }
        ]
    }

    with open(registry_path, "w", encoding="utf-8") as file:
        json.dump(registry_data, file)

    generator = WeeklyIntelligenceReportGenerator(registry_path=registry_path)

    report_path = generator.generate()

    content = report_path.read_text(encoding="utf-8")

    assert "Total Research Runs: 1" in content
    assert "Accepted Opportunities: 2" in content
    assert "- home services: 1" in content
    assert "- smallbusiness: 1" in content
    assert "reports/opportunities/lead_follow-up_automation.md" in content


def test_weekly_report_blocks_registry_path_traversal():
    with pytest.raises(WeeklyIntelligenceReportError):
        WeeklyIntelligenceReportGenerator(registry_path="../../unsafe.json")


def test_weekly_report_blocks_non_json_registry():
    with pytest.raises(WeeklyIntelligenceReportError):
        WeeklyIntelligenceReportGenerator(
            registry_path="reports/intelligence/research_run_index.txt"
        )


def test_weekly_report_blocks_output_outside_weekly_folder():
    with pytest.raises(WeeklyIntelligenceReportError):
        WeeklyIntelligenceReportGenerator(output_dir="reports/intelligence")
