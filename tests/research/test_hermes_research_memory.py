import json

import pytest

from src.hermes.research_memory import (
    HermesMemoryError,
    HermesResearchMemoryHook,
)


def test_hermes_memory_hook_builds_and_writes_record():
    hook = HermesResearchMemoryHook()

    record = hook.build_record(
        source="reddit",
        industry="home services",
        pain_point="Clients stop replying after quotes.",
        recommendation="VALIDATE_FIRST",
        score=7.2,
        report_path="reports/opportunities/lead_follow-up_automation.md",
    )

    memory_path = hook.write_record(record)

    assert memory_path.exists()
    assert memory_path.suffix == ".json"

    data = json.loads(memory_path.read_text(encoding="utf-8"))

    assert data["source"] == "reddit"
    assert data["industry"] == "home services"
    assert data["recommendation"] == "VALIDATE_FIRST"
    assert data["score"] == 7.2


def test_hermes_memory_hook_blocks_empty_text():
    hook = HermesResearchMemoryHook()

    with pytest.raises(HermesMemoryError):
        hook.build_record(
            source="",
            industry="home services",
            pain_point="Clients stop replying after quotes.",
            recommendation="VALIDATE_FIRST",
            score=7.2,
            report_path="reports/opportunities/lead_follow-up_automation.md",
        )


def test_hermes_memory_hook_blocks_secret_like_text():
    hook = HermesResearchMemoryHook()

    with pytest.raises(HermesMemoryError):
        hook.build_record(
            source="reddit",
            industry="home services",
            pain_point="The api_key is exposed in logs.",
            recommendation="VALIDATE_FIRST",
            score=7.2,
            report_path="reports/opportunities/lead_follow-up_automation.md",
        )


def test_hermes_memory_hook_blocks_score_outside_range():
    hook = HermesResearchMemoryHook()

    with pytest.raises(HermesMemoryError):
        hook.build_record(
            source="reddit",
            industry="home services",
            pain_point="Clients stop replying after quotes.",
            recommendation="VALIDATE_FIRST",
            score=11,
            report_path="reports/opportunities/lead_follow-up_automation.md",
        )


def test_hermes_memory_hook_blocks_memory_dir_path_traversal():
    with pytest.raises(HermesMemoryError):
        HermesResearchMemoryHook(memory_dir="../../unsafe")


def test_hermes_memory_hook_blocks_report_path_outside_reports():
    hook = HermesResearchMemoryHook()

    with pytest.raises(HermesMemoryError):
        hook.build_record(
            source="reddit",
            industry="home services",
            pain_point="Clients stop replying after quotes.",
            recommendation="VALIDATE_FIRST",
            score=7.2,
            report_path="../../protected/SECURITY_RULES.md",
        )


def test_hermes_memory_hook_blocks_non_markdown_report_path():
    hook = HermesResearchMemoryHook()

    with pytest.raises(HermesMemoryError):
        hook.build_record(
            source="reddit",
            industry="home services",
            pain_point="Clients stop replying after quotes.",
            recommendation="VALIDATE_FIRST",
            score=7.2,
            report_path="reports/opportunities/not_a_report.json",
        )
