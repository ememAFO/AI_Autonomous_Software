from pathlib import Path
import pytest

from src.security.protected_files import build_manifest, verify_manifest, ProtectedFileIntegrityError


def test_detects_protected_file_change(tmp_path: Path):
    protected = tmp_path / "protected"
    protected.mkdir()
    rules = protected / "SECURITY_RULES.md"
    rules.write_text("do not change", encoding="utf-8")
    manifest = build_manifest(tmp_path)

    rules.write_text("changed", encoding="utf-8")

    with pytest.raises(ProtectedFileIntegrityError):
        verify_manifest(tmp_path, manifest)
