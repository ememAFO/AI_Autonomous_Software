from pathlib import Path
import pytest

from src.sandbox_runner.runner import SandboxRunner, SandboxError


def test_blocks_unapproved_command(tmp_path: Path):
    runner = SandboxRunner(tmp_path)
    with pytest.raises(SandboxError):
        runner.run(["bash", "-lc", "echo unsafe"])


def test_blocks_dangerous_token(tmp_path: Path):
    runner = SandboxRunner(tmp_path, allowed_commands={"python"})
    with pytest.raises(SandboxError):
        runner.run(["python", "-c", "print('x')", "sudo"])
