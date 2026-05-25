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


def test_memory_trend_report_blocks_output_outside_intelligence():
    with pytest.raises(MemoryTrendReportError):
        HermesMemoryTrendReportGenerator(output_dir="../../unsafe")
