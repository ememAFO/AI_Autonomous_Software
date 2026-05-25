from pathlib import Path


class PathNormalizerError(Exception):
    pass


class ProjectPathNormalizer:
    """
    Normalizes project paths for clean reports.

    Purpose:
    - convert absolute project paths into relative paths
    - keep reports readable
    - prevent leaking full local machine paths in generated reports
    """

    def __init__(self, project_root: str | Path | None = None):
        self.project_root = Path(project_root or Path.cwd()).resolve()

    def normalize(self, value: str) -> str:
        if not value:
            return value

        path = Path(value)

        if not path.is_absolute():
            return value

        resolved_path = path.resolve()

        try:
            return str(resolved_path.relative_to(self.project_root))
        except ValueError:
            raise PathNormalizerError(
                "Path is outside project root and cannot be safely normalized"
            )

    def normalize_many(self, values: list[str]) -> list[str]:
        return [self.normalize(value) for value in values]
