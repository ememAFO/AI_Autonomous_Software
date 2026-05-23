import json

import pytest

from src.research.run_manifest import (
    ResearchRunManifestWriter,
    RunManifestError,
)


def test_run_manifest_writer_creates_manifest_file():
    writer = ResearchRunManifestWriter()

    manifest = writer.create_manifest(
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

    manifest_path = writer.write(manifest)

    assert manifest_path.exists()
    assert manifest_path.suffix == ".json"

    data = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert data["run_id"] == manifest.run_id
    assert data["status"] == "success"
    assert data["query"] == "manual follow up"
    assert data["subreddit"] == "smallbusiness"
    assert data["final_workflow_stage"] == "REPORT"
    assert data["processed_count"] == 2
    assert data["accepted_count"] == 2
    assert data["rejected_count"] == 0


def test_run_manifest_blocks_path_traversal_output_dir():
    with pytest.raises(RunManifestError):
        ResearchRunManifestWriter(output_dir="../../unsafe")


def test_run_manifest_blocks_output_outside_allowed_folder():
    with pytest.raises(RunManifestError):
        ResearchRunManifestWriter(output_dir="reports/opportunities")


def test_run_manifest_sanitizes_filename_values():
    writer = ResearchRunManifestWriter()

    manifest = writer.create_manifest(
        status="success",
        query="../manual follow up!!",
        subreddit="../smallbusiness",
        industry="home services",
        final_workflow_stage="REPORT",
        processed_count=2,
        accepted_count=2,
        rejected_count=0,
        report_paths=[],
    )

    manifest_path = writer.write(manifest)

    assert ".." not in manifest_path.name
    assert "/" not in manifest_path.name
    assert manifest_path.suffix == ".json"
