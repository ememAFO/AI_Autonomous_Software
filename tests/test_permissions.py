from pathlib import Path
import pytest

from src.security.permissions import PermissionPolicy, PermissionError


def test_allows_editable_src_path(tmp_path: Path):
    policy = PermissionPolicy(tmp_path)
    assert policy.assert_edit_allowed("src/example.py") == tmp_path / "src" / "example.py"


def test_blocks_protected_path(tmp_path: Path):
    policy = PermissionPolicy(tmp_path)
    with pytest.raises(PermissionError):
        policy.assert_edit_allowed("protected/SECURITY_RULES.md")


def test_blocks_path_traversal(tmp_path: Path):
    policy = PermissionPolicy(tmp_path)
    with pytest.raises(PermissionError):
        policy.assert_edit_allowed("../outside.txt")


def test_blocks_sensitive_secret_path(tmp_path: Path):
    policy = PermissionPolicy(tmp_path)
    with pytest.raises(PermissionError):
        policy.assert_edit_allowed("src/.env")
