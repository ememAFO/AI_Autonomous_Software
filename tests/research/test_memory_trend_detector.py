import json

import pytest

from src.hermes.memory_trend_detector import (
    HermesMemoryTrendDetector,
    MemoryTrendDetectorError,
)
from src.hermes.memory_trend_report import (
    HermesMemoryTrendReportGenerator,
    MemoryTrendReportError,
)

from src.hermes.memory_trend_detector import MemoryTrendFilter


def test_memory_trend_detector_summarizes_records():
    memory_dir = "data/hermes/research_memory/test_trends"
    record_path = f"{memory_dir}/record.json"

    import os
    os.makedirs(memory_dir, exist_ok=True)

    with open(record_path, "w", encoding="utf-8") as file:
        json.dump(
            {
                "source": "reddit",
                "industry": "sales",
                "pain_point": "Sales teams lose leads because manual follow up is slow.",
                "recommendation": "BUILD_NOW",
                "score": 8.5,
                "report_path": "reports/opportunities/lead_follow-up_automation.md",
                "timestamp": "2026-05-25T22:00:00+00:00",
            },
            file,
        )

    summary = HermesMemoryTrendDetector(memory_dir=memory_dir).summarize()

    assert summary.total_records >= 1
    assert ("sales", 1) in summary.top_industries
    assert ("BUILD_NOW", 1) in summary.top_recommendations
    assert any(term == "lead" for term, _ in summary.repeated_pain_terms)
    assert summary.high_confidence_records


def test_memory_trend_detector_ignores_malformed_json():
    memory_dir = "data/hermes/research_memory/test_malformed"

    import os
    os.makedirs(memory_dir, exist_ok=True)

    with open(f"{memory_dir}/bad.json", "w", encoding="utf-8") as file:
        file.write("{not valid json")

    summary = HermesMemoryTrendDetector(memory_dir=memory_dir).summarize()

    assert summary.total_records == 0


def test_memory_trend_detector_blocks_path_traversal():
    with pytest.raises(MemoryTrendDetectorError):
        HermesMemoryTrendDetector(memory_dir="../../unsafe")


def test_memory_trend_report_generator_creates_markdown_report():
    memory_dir = "data/hermes/research_memory/test_report"

    import os
    os.makedirs(memory_dir, exist_ok=True)

    with open(f"{memory_dir}/record.json", "w", encoding="utf-8") as file:
        json.dump(
            {
                "source": "reddit",
                "industry": "saas",
                "pain_point": "Users complain about missing integration and poor onboarding.",
                "recommendation": "BUILD_NOW",
                "score": 8.2,
                "report_path": "reports/opportunities/integration_gap.md",
                "timestamp": "2026-05-25T22:00:00+00:00",
            },
            file,
        )

    summary = HermesMemoryTrendDetector(memory_dir=memory_dir).summarize()

    report_path = HermesMemoryTrendReportGenerator(
        output_dir="reports/intelligence/test_trends"
    ).generate(summary)

    assert report_path.exists()

    content = report_path.read_text(encoding="utf-8")

    assert "# Hermes Memory Trend Report" in content
    assert "Total Memory Records" in content
    assert "Top Industries" in content
    assert "Repeated Pain Terms" in content
    assert "High-Confidence Opportunity Themes" in content
    assert "High-Confidence Themes" in content
    assert "Filtered Memory Records" in content
    assert "Filters Applied" in content
    assert "Top Sources" in content
    assert "Filtered Themes" in content
    assert "Filtered Opportunity Themes" in content

def test_memory_trend_report_blocks_output_outside_intelligence():
    with pytest.raises(MemoryTrendReportError):
        HermesMemoryTrendReportGenerator(output_dir="../../unsafe")

def test_memory_trend_detector_groups_repeated_high_confidence_themes():
    memory_dir = "data/hermes/research_memory/test_theme_grouping"

    import os
    os.makedirs(memory_dir, exist_ok=True)

    records = [
        {
            "source": "reddit",
            "industry": "sales",
            "pain_point": "Sales teams lose leads because manual follow up is slow.",
            "recommendation": "BUILD_NOW",
            "score": 8.5,
            "report_path": "reports/opportunities/lead_follow-up_automation.md",
            "timestamp": "2026-05-25T22:00:00+00:00",
        },
        {
            "source": "reddit",
            "industry": "home services",
            "pain_point": "Small businesses lose leads because manual follow up after quotes is poor.",
            "recommendation": "BUILD_NOW",
            "score": 8.1,
            "report_path": "reports/opportunities/lead_follow-up_automation.md",
            "timestamp": "2026-05-25T22:01:00+00:00",
        },
    ]

    for index, record in enumerate(records):
        with open(f"{memory_dir}/record_{index}.json", "w", encoding="utf-8") as file:
            json.dump(record, file)

    summary = HermesMemoryTrendDetector(memory_dir=memory_dir).summarize()

    assert summary.high_confidence_themes
    assert summary.high_confidence_themes[0].record_count == 2
    assert "lead" in summary.high_confidence_themes[0].theme
    assert summary.high_confidence_themes[0].average_score == 8.3

def test_memory_trend_detector_filters_by_industry():
    memory_dir = "data/hermes/research_memory/test_filter_industry"

    import os
    os.makedirs(memory_dir, exist_ok=True)

    records = [
        {
            "source": "reddit",
            "industry": "sales",
            "pain_point": "Sales teams lose leads because manual follow up is slow.",
            "recommendation": "BUILD_NOW",
            "score": 8.5,
            "report_path": "reports/opportunities/lead_follow-up_automation.md",
            "timestamp": "2026-05-25T22:00:00+00:00",
        },
        {
            "source": "review_site",
            "industry": "saas",
            "pain_point": "The integration creates duplicate contacts and is difficult to resolve.",
            "recommendation": "VALIDATE_FIRST",
            "score": 7.1,
            "report_path": "reports/opportunities/integration_workflow_pain.md",
            "timestamp": "2026-05-25T22:01:00+00:00",
        },
    ]

    for index, record in enumerate(records):
        with open(f"{memory_dir}/record_{index}.json", "w", encoding="utf-8") as file:
            json.dump(record, file)

    summary = HermesMemoryTrendDetector(memory_dir=memory_dir).summarize(
        filters=MemoryTrendFilter(industry="saas")
    )

    assert summary.total_records == 2
    assert summary.filtered_records == 1
    assert summary.top_industries == [("saas", 1)]
    assert summary.filters.industry == "saas"


def test_memory_trend_detector_filters_by_source_and_excludes_source():
    memory_dir = "data/hermes/research_memory/test_filter_source"

    import os
    os.makedirs(memory_dir, exist_ok=True)

    records = [
        {
            "source": "reddit",
            "industry": "sales",
            "pain_point": "Sales teams lose leads because manual follow up is slow.",
            "recommendation": "BUILD_NOW",
            "score": 8.5,
            "report_path": "reports/opportunities/lead_follow-up_automation.md",
            "timestamp": "2026-05-25T22:00:00+00:00",
        },
        {
            "source": "review_site",
            "industry": "saas",
            "pain_point": "The integration creates duplicate contacts and is difficult to resolve.",
            "recommendation": "VALIDATE_FIRST",
            "score": 8.1,
            "report_path": "reports/opportunities/integration_workflow_pain.md",
            "timestamp": "2026-05-25T22:01:00+00:00",
        },
    ]

    for index, record in enumerate(records):
        with open(f"{memory_dir}/record_{index}.json", "w", encoding="utf-8") as file:
            json.dump(record, file)

    source_summary = HermesMemoryTrendDetector(memory_dir=memory_dir).summarize(
        filters=MemoryTrendFilter(source="review_site")
    )

    exclude_summary = HermesMemoryTrendDetector(memory_dir=memory_dir).summarize(
        filters=MemoryTrendFilter(exclude_source="reddit")
    )

    assert source_summary.filtered_records == 1
    assert source_summary.top_sources == [("review_site", 1)]
    assert exclude_summary.filtered_records == 1
    assert exclude_summary.top_sources == [("review_site", 1)]


def test_memory_trend_detector_filters_by_recommendation():
    memory_dir = "data/hermes/research_memory/test_filter_recommendation"

    import os
    os.makedirs(memory_dir, exist_ok=True)

    records = [
        {
            "source": "reddit",
            "industry": "sales",
            "pain_point": "Sales teams lose leads because manual follow up is slow.",
            "recommendation": "BUILD_NOW",
            "score": 8.5,
            "report_path": "reports/opportunities/lead_follow-up_automation.md",
            "timestamp": "2026-05-25T22:00:00+00:00",
        },
        {
            "source": "review_site",
            "industry": "saas",
            "pain_point": "The integration creates duplicate contacts and is difficult to resolve.",
            "recommendation": "VALIDATE_FIRST",
            "score": 8.1,
            "report_path": "reports/opportunities/integration_workflow_pain.md",
            "timestamp": "2026-05-25T22:01:00+00:00",
        },
    ]

    for index, record in enumerate(records):
        with open(f"{memory_dir}/record_{index}.json", "w", encoding="utf-8") as file:
            json.dump(record, file)

    summary = HermesMemoryTrendDetector(memory_dir=memory_dir).summarize(
        filters=MemoryTrendFilter(recommendation="VALIDATE_FIRST")
    )

    assert summary.filtered_records == 1
    assert summary.top_recommendations == [("VALIDATE_FIRST", 1)]

def test_memory_trend_detector_builds_filtered_themes_below_high_confidence():
    memory_dir = "data/hermes/research_memory/test_filtered_themes"

    import os
    os.makedirs(memory_dir, exist_ok=True)

    records = [
        {
            "source": "review_site",
            "industry": "saas",
            "pain_point": "The integration creates duplicate contacts and is difficult to resolve.",
            "recommendation": "VALIDATE_FIRST",
            "score": 7.1,
            "report_path": "reports/opportunities/integration_workflow_pain.md",
            "timestamp": "2026-05-25T22:00:00+00:00",
        },
        {
            "source": "review_site",
            "industry": "saas",
            "pain_point": "The integration keeps creating duplicate contacts during sync.",
            "recommendation": "VALIDATE_FIRST",
            "score": 7.2,
            "report_path": "reports/opportunities/integration_workflow_pain.md",
            "timestamp": "2026-05-25T22:01:00+00:00",
        },
    ]

    for index, record in enumerate(records):
        with open(f"{memory_dir}/record_{index}.json", "w", encoding="utf-8") as file:
            json.dump(record, file)

    summary = HermesMemoryTrendDetector(memory_dir=memory_dir).summarize()

    assert summary.filtered_records == 2
    assert summary.filtered_themes
    assert summary.filtered_themes[0].theme == "integration workflow"
    assert summary.filtered_themes[0].record_count == 2
    assert summary.high_confidence_records == []
    assert summary.high_confidence_themes == []
