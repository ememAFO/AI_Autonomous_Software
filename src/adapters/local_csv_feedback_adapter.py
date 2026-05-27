import csv
from dataclasses import dataclass
from pathlib import Path


class LocalCSVFeedbackAdapterError(Exception):
    pass


@dataclass(frozen=True)
class LocalFeedbackItem:
    source_file: str
    source_type: str
    text: str
    industry: str
    metadata: dict[str, str]


@dataclass(frozen=True)
class LocalCSVFeedbackLoadResult:
    source_path: Path
    text_column: str
    loaded_count: int
    skipped_count: int
    items: list[LocalFeedbackItem]


class LocalCSVFeedbackAdapter:
    """
    Safely loads local CSV feedback/review datasets.

    Security rules:
    - Reads only from data/raw/external_feedback.
    - Reads CSV files only.
    - Does not execute file content.
    - Limits rows per file.
    - Detects known text columns automatically.
    - Keeps metadata as strings only.
    """

    DEFAULT_ALLOWED_ROOT = Path("data/raw/external_feedback")

    TEXT_COLUMN_CANDIDATES = [
        "Content",
        "Reviews",
        "Review",
        "review",
        "review_text",
        "Review Text",
        "text",
        "Text",
        "comment",
        "Comment",
        "message",
        "Message",
        "description",
        "Description",
        "body",
        "Body",
    ]

    MAX_ROWS_PER_FILE = 250

    def __init__(self, allowed_root: str | Path = DEFAULT_ALLOWED_ROOT):
        self.allowed_root = self._validate_allowed_root(Path(allowed_root))

    def load_file(
        self,
        csv_path: str | Path,
        *,
        industry: str,
        source_type: str = "local_csv_feedback",
        max_rows: int = 50,
    ) -> LocalCSVFeedbackLoadResult:
        if not industry or not industry.strip():
            raise LocalCSVFeedbackAdapterError("Industry cannot be empty")

        if not source_type or not source_type.strip():
            raise LocalCSVFeedbackAdapterError("Source type cannot be empty")

        self._validate_max_rows(max_rows)

        resolved_path = self._validate_csv_path(Path(csv_path))

        items: list[LocalFeedbackItem] = []
        skipped_count = 0

        with resolved_path.open("r", encoding="utf-8-sig", newline="") as file:
            reader = csv.DictReader(file)

            if not reader.fieldnames:
                raise LocalCSVFeedbackAdapterError("CSV file has no header row")

            text_column = self._detect_text_column(reader.fieldnames)

            for row in reader:
                if len(items) >= max_rows:
                    break

                raw_text = row.get(text_column, "")
                text = self._clean_text(raw_text)

                if not text:
                    skipped_count += 1
                    continue

                items.append(
                    LocalFeedbackItem(
                        source_file=str(resolved_path),
                        source_type=source_type,
                        text=text,
                        industry=industry.strip(),
                        metadata=self._clean_metadata(row),
                    )
                )

        return LocalCSVFeedbackLoadResult(
            source_path=resolved_path,
            text_column=text_column,
            loaded_count=len(items),
            skipped_count=skipped_count,
            items=items,
        )

    def _validate_allowed_root(self, allowed_root: Path) -> Path:
        resolved = allowed_root.resolve()
        project_root = Path.cwd().resolve()
        expected_root = (project_root / "data" / "raw" / "external_feedback").resolve()

        if not str(resolved).startswith(str(expected_root)):
            raise LocalCSVFeedbackAdapterError(
                "Allowed root must stay inside data/raw/external_feedback"
            )

        return resolved

    def _validate_csv_path(self, csv_path: Path) -> Path:
        resolved = csv_path.resolve()

        if not str(resolved).startswith(str(self.allowed_root)):
            raise LocalCSVFeedbackAdapterError(
                "CSV path must stay inside data/raw/external_feedback"
            )

        if resolved.suffix.lower() != ".csv":
            raise LocalCSVFeedbackAdapterError("Only CSV files are supported")

        if not resolved.exists():
            raise LocalCSVFeedbackAdapterError("CSV file does not exist")

        if not resolved.is_file():
            raise LocalCSVFeedbackAdapterError("CSV path must point to a file")

        return resolved

    def _validate_max_rows(self, max_rows: int) -> None:
        if max_rows < 1:
            raise LocalCSVFeedbackAdapterError("max_rows must be at least 1")

        if max_rows > self.MAX_ROWS_PER_FILE:
            raise LocalCSVFeedbackAdapterError(
                f"max_rows cannot exceed {self.MAX_ROWS_PER_FILE}"
            )

    def _detect_text_column(self, columns: list[str]) -> str:
        normalized_columns = {column.lower(): column for column in columns}

        for candidate in self.TEXT_COLUMN_CANDIDATES:
            match = normalized_columns.get(candidate.lower())

            if match:
                return match

        raise LocalCSVFeedbackAdapterError(
            "No supported text column found. Expected one of: "
            + ", ".join(self.TEXT_COLUMN_CANDIDATES)
        )

    def _clean_text(self, value: str | None) -> str:
        if value is None:
            return ""

        return " ".join(str(value).replace("\n", " ").split()).strip()

    def _clean_metadata(self, row: dict[str, str]) -> dict[str, str]:
        metadata: dict[str, str] = {}

        for key, value in row.items():
            clean_key = str(key).strip()
            clean_value = self._clean_text(value)

            if clean_key and clean_value:
                metadata[clean_key] = clean_value[:500]

        return metadata
