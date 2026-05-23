import json

import pytest

from src.research.run_manifest import ResearchRunManifestWriter
from src.research.run_registry import (
    ResearchRunRegistryError,
    ResearchRunRegistryWriter,
)


def test_run_registry_adds_manifest_to_index():
    manifest_writer = ResearchRunManifestWriter()

    manifest = manifest_writer.create_manifest(
        status="success",
        query="manual follow up",
        subreddit="smallbusiness",
        industry="home services",
        final_workflow_stage="REPORT",
        processed_count=2,
        accepted_count=2,
        rejected_count=0,
        report_paths=[
            "reports/opportunities/lead_follow-up_automation.md",
        ],
    )

    manifest_path = manifest_writer.write(manifest)

    registry_writer = ResearchRunRegistryWriter()
    registry_path = registry_writer.add_run(
        manifest=manifest,
        manifest_path=str(manifest_path),
    )

    assert registry_path.exists()

    data = json.loads(registry_path.read_text(encoding="utf-8"))

    assert "runs" in data
    assert data["runs"]

    latest_run = data["runs"][-1]

    assert latest_run["run_id"] == manifest.run_id
    assert latest_run["status"] == "success"
    assert latest_run["query"] == "manual follow up"
    assert latest_run["subreddit"] == "smallbusiness"
    assert latest_run["manifest_path"] == str(manifest_path)


def test_run_registry_blocks_path_traversal():
    with pytest.raises(ResearchRunRegistryError):
        ResearchRunRegistryWriter(registry_path="../../unsafe.json")


def test_run_registry_blocks_non_json_file():
    with pytest.raises(ResearchRunRegistryError):
        ResearchRunRegistryWriter(
            registry_path="reports/intelligence/research_run_index.txt"
        )


def test_run_registry_preserves_existing_runs():
    manifest_writer = ResearchRunManifestWriter()
    registry_writer = ResearchRunRegistryWriter(
        registry_path="reports/intelligence/test_research_run_index.json"
    )

    first_manifest = manifest_writer.create_manifest(
        status="success",
        query="manual follow up",
        subreddit="smallbusiness",
        industry="home services",
        final_workflow_stage="REPORT",
        processed_count=2,
        accepted_count=2,
        rejected_count=0,
        report_paths=[],
    )

    second_manifest = manifest_writer.create_manifest(
        status="success",
        query="missed bookings",
        subreddit="smallbusiness",
        industry="clinics",
        final_workflow_stage="REPORT",
        processed_count=2,
        accepted_count=1,
        rejected_count=1,
        report_paths=[],
    )

    registry_writer.add_run(
        manifest=first_manifest,
        manifest_path="reports/intelligence/runs/first.json",
    )

    registry_path = registry_writer.add_run(
        manifest=second_manifest,
        manifest_path="reports/intelligence/runs/second.json",
    )

    data = json.loads(registry_path.read_text(encoding="utf-8"))

    assert len(data["runs"]) >= 2
    assert data["runs"][-2]["query"] == "manual follow up"
    assert data["runs"][-1]["query"] == "missed bookings"
