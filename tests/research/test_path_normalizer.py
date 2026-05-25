from pathlib import Path

import pytest

from src.utils.path_normalizer import ProjectPathNormalizer, PathNormalizerError


def test_path_normalizer_keeps_relative_path_unchanged():
    normalizer = ProjectPathNormalizer()

    result = normalizer.normalize("reports/opportunities/example.md")

    assert result == "reports/opportunities/example.md"


def test_path_normalizer_converts_absolute_project_path_to_relative():
    project_root = Path.cwd()
    absolute_path = project_root / "reports" / "opportunities" / "example.md"

    normalizer = ProjectPathNormalizer(project_root=project_root)

    result = normalizer.normalize(str(absolute_path))

    assert result == "reports/opportunities/example.md"


def test_path_normalizer_blocks_path_outside_project_root():
    normalizer = ProjectPathNormalizer(project_root=Path.cwd())

    with pytest.raises(PathNormalizerError):
        normalizer.normalize("/etc/passwd")


def test_path_normalizer_normalizes_many_paths():
    project_root = Path.cwd()

    values = [
        "reports/opportunities/a.md",
        str(project_root / "reports" / "opportunities" / "b.md"),
    ]

    result = ProjectPathNormalizer(project_root=project_root).normalize_many(values)

    assert result == [
        "reports/opportunities/a.md",
        "reports/opportunities/b.md",
    ]
