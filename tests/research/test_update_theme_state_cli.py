import subprocess
from pathlib import Path


SCRIPT = "scripts/update_theme_state.py"
REGISTRY_PATH = Path("reports/intelligence/theme_state_registry.json")


def clean_registry() -> None:
    if REGISTRY_PATH.exists():
        REGISTRY_PATH.unlink()


def test_update_theme_state_cli_registers_theme():
    clean_registry()

    result = subprocess.run(
        [
            "python",
            SCRIPT,
            "--action",
            "register",
            "--theme-id",
            "lead_follow_up_001",
            "--theme-name",
            "lead + follow up",
            "--trigger",
            "test_register",
            "--reason",
            "Testing registration.",
            "--changed-by",
            "test",
            "--related-artifact-id",
            "test_artifact",
            "--policy-version",
            "2026-06-08.v1",
            "--run-id",
            "test_run_001",
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    assert "Theme Registered" in result.stdout
    assert "RESEARCHED" in result.stdout


def test_update_theme_state_cli_transitions_theme():
    clean_registry()

    subprocess.run(
        [
            "python",
            SCRIPT,
            "--action",
            "register",
            "--theme-id",
            "lead_follow_up_001",
            "--theme-name",
            "lead + follow up",
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    result = subprocess.run(
        [
            "python",
            SCRIPT,
            "--action",
            "transition",
            "--theme-id",
            "lead_follow_up_001",
            "--theme-name",
            "lead + follow up",
            "--new-state",
            "VALIDATION_READY",
            "--trigger",
            "test_transition",
            "--reason",
            "Testing transition.",
            "--changed-by",
            "test",
            "--related-artifact-id",
            "test_artifact",
            "--policy-version",
            "2026-06-08.v1",
            "--run-id",
            "test_run_002",
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    assert "Theme State Updated" in result.stdout
    assert "VALIDATION_READY" in result.stdout


def test_update_theme_state_cli_blocks_invalid_transition():
    clean_registry()

    subprocess.run(
        [
            "python",
            SCRIPT,
            "--action",
            "register",
            "--theme-id",
            "lead_follow_up_001",
            "--theme-name",
            "lead + follow up",
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    result = subprocess.run(
        [
            "python",
            SCRIPT,
            "--action",
            "transition",
            "--theme-id",
            "lead_follow_up_001",
            "--theme-name",
            "lead + follow up",
            "--new-state",
            "READY_FOR_REVIEW",
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 1
    assert "Theme state update blocked" in result.stderr


def test_update_theme_state_cli_shows_current_state():
    clean_registry()

    subprocess.run(
        [
            "python",
            SCRIPT,
            "--action",
            "register",
            "--theme-id",
            "lead_follow_up_001",
            "--theme-name",
            "lead + follow up",
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    result = subprocess.run(
        [
            "python",
            SCRIPT,
            "--action",
            "current-state",
            "--theme-id",
            "lead_follow_up_001",
            "--theme-name",
            "lead + follow up",
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    assert "Current State: RESEARCHED" in result.stdout


def test_update_theme_state_cli_shows_history():
    clean_registry()

    subprocess.run(
        [
            "python",
            SCRIPT,
            "--action",
            "register",
            "--theme-id",
            "lead_follow_up_001",
            "--theme-name",
            "lead + follow up",
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    result = subprocess.run(
        [
            "python",
            SCRIPT,
            "--action",
            "history",
            "--theme-id",
            "lead_follow_up_001",
            "--theme-name",
            "lead + follow up",
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    assert "Theme State History" in result.stdout
    assert "RESEARCHED" in result.stdout
