import csv
from dataclasses import dataclass, field
from pathlib import Path

from src.utils.label_normalizer import LabelNormalizer
from src.utils.path_normalizer import PathNormalizerError, ProjectPathNormalizer


class LocalDatasetProfilerError(Exception):
    pass


@dataclass(frozen=True)
class LocalDatasetProfile:
    source_path: str
    row_count: int
    columns: list[str]
    detected_text_column: str | None
    detected_rating_column: str | None
    detected_date_column: str | None
    detected_product_column: str | None
    detected_vendor_column: str | None
    sample_text_preview: str | None
    empty_text_rows: int
    suggested_source_type: str
    suggested_industry: str
    suggested_source_quality: str
    recommended_first_run_rows: int
    notes: list[str] = field(default_factory=list)


class LocalDatasetProfiler:
    """
    Profiles a local CSV feedback dataset before ingestion.

    Purpose:
    - inspect dataset structure before running research
    - detect useful columns
    - suggest industry/source metadata
    - recommend safe first-run size
    - avoid blindly processing noisy data

    Security:
    - reads only local CSV files
    - does not execute file content
    - does not write reports or memory
    """

    TEXT_COLUMN_CANDIDATES = [
        "text",
        "review",
        "content",
        "body",
        "comment",
        "description",
        "review_text",
        "review body",
        "message",
    ]

    RATING_COLUMN_CANDIDATES = [
        "stars",
        "rating",
        "score",
        "review_rating",
    ]

    DATE_COLUMN_CANDIDATES = [
        "date",
        "created_at",
        "review_date",
        "posted_at",
        "timestamp",
    ]

    PRODUCT_COLUMN_CANDIDATES = [
        "product_name",
        "product",
        "app",
        "app_name",
        "software",
        "tool",
    ]

    VENDOR_COLUMN_CANDIDATES = [
        "vendor_name",
        "vendor",
        "company",
        "developer",
        "provider",
    ]

    def __init__(self):
        self.path_normalizer = ProjectPathNormalizer()
        self.label_normalizer = LabelNormalizer()

    def profile(self, file_path: str | Path) -> LocalDatasetProfile:
        path = Path(file_path)

        if not path.exists():
            raise LocalDatasetProfilerError(f"Dataset file does not exist: {file_path}")

        if path.suffix.lower() != ".csv":
            raise LocalDatasetProfilerError("Local dataset profiler currently supports CSV files only")

        try:
            normalized_path = self.path_normalizer.normalize(str(path))
        except PathNormalizerError:
            normalized_path = str(path)

        with path.open("r", encoding="utf-8-sig", newline="") as file:
            reader = csv.DictReader(file)

            columns = reader.fieldnames or []

            if not columns:
                raise LocalDatasetProfilerError("CSV file has no header columns")

            detected_text_column = self._detect_column(columns, self.TEXT_COLUMN_CANDIDATES)
            detected_rating_column = self._detect_column(columns, self.RATING_COLUMN_CANDIDATES)
            detected_date_column = self._detect_column(columns, self.DATE_COLUMN_CANDIDATES)
            detected_product_column = self._detect_column(columns, self.PRODUCT_COLUMN_CANDIDATES)
            detected_vendor_column = self._detect_column(columns, self.VENDOR_COLUMN_CANDIDATES)

            row_count = 0
            empty_text_rows = 0
            sample_text_preview = None

            for row in reader:
                row_count += 1

                if detected_text_column:
                    text = str(row.get(detected_text_column, "") or "").strip()

                    if not text:
                        empty_text_rows += 1
                    elif sample_text_preview is None:
                        sample_text_preview = text[:300]

        suggested_source_type = self._suggest_source_type(path, columns)
        suggested_industry = self._suggest_industry(path, columns)
        suggested_source_quality = self._suggest_source_quality(
            suggested_source_type=suggested_source_type,
            detected_product_column=detected_product_column,
            detected_vendor_column=detected_vendor_column,
        )

        notes = self._notes(
            row_count=row_count,
            detected_text_column=detected_text_column,
            detected_rating_column=detected_rating_column,
            detected_date_column=detected_date_column,
            detected_product_column=detected_product_column,
            detected_vendor_column=detected_vendor_column,
            empty_text_rows=empty_text_rows,
            suggested_source_quality=suggested_source_quality,
        )

        return LocalDatasetProfile(
            source_path=normalized_path,
            row_count=row_count,
            columns=columns,
            detected_text_column=detected_text_column,
            detected_rating_column=detected_rating_column,
            detected_date_column=detected_date_column,
            detected_product_column=detected_product_column,
            detected_vendor_column=detected_vendor_column,
            sample_text_preview=sample_text_preview,
            empty_text_rows=empty_text_rows,
            suggested_source_type=suggested_source_type,
            suggested_industry=suggested_industry,
            suggested_source_quality=suggested_source_quality,
            recommended_first_run_rows=self._recommended_first_run_rows(row_count),
            notes=notes,
        )

    def _detect_column(self, columns: list[str], candidates: list[str]) -> str | None:
        normalized_lookup = {
            self.label_normalizer.normalize(column): column
            for column in columns
        }

        for candidate in candidates:
            normalized_candidate = self.label_normalizer.normalize(candidate)

            if normalized_candidate in normalized_lookup:
                return normalized_lookup[normalized_candidate]

        return None

    def _suggest_source_type(self, path: Path, columns: list[str]) -> str:
        text = str(path).lower()

        if "g2" in text:
            return "g2_reviews"

        if "capterra" in text:
            return "capterra_reviews"

        if "trustradius" in text:
            return "trustradius_reviews"

        if "trustpilot" in text:
            return "trustpilot_reviews"

        if "app-store" in text or "app_store" in text:
            return "app_store"

        if "google-play" in text or "google_play" in text:
            return "google_play"

        if "github" in text or "issue" in text or "jira" in text:
            return "issue_tracker"

        if self._detect_column(columns, ["product_name", "vendor_name", "stars"]):
            return "software_reviews"

        return "local_feedback"

    def _suggest_industry(self, path: Path, columns: list[str]) -> str:
        text = str(path).lower()

        if "g2" in text or "software" in text or "saas" in text:
            return "saas"

        if "airline" in text or "travel" in text:
            return "airline"

        if "crm" in text or "sales" in text:
            return "sales"

        if "accounting" in text or "invoice" in text or "finance" in text:
            return "finance"

        if self._detect_column(columns, ["product_name", "vendor_name"]):
            return "saas"

        return "general"

    def _suggest_source_quality(
        self,
        *,
        suggested_source_type: str,
        detected_product_column: str | None,
        detected_vendor_column: str | None,
    ) -> str:
        if suggested_source_type in {
            "g2_reviews",
            "capterra_reviews",
            "trustradius_reviews",
            "issue_tracker",
        }:
            return "core_evidence"

        if suggested_source_type in {
            "software_reviews",
            "google_play",
            "app_store",
        } and (detected_product_column or detected_vendor_column):
            return "supporting_evidence"

        if suggested_source_type in {
            "trustpilot_reviews",
        }:
            return "operational_evidence"

        return "exploratory_evidence"

    def _recommended_first_run_rows(self, row_count: int) -> int:
        if row_count <= 20:
            return row_count

        if row_count <= 100:
            return 20

        return 50

    def _notes(
        self,
        *,
        row_count: int,
        detected_text_column: str | None,
        detected_rating_column: str | None,
        detected_date_column: str | None,
        detected_product_column: str | None,
        detected_vendor_column: str | None,
        empty_text_rows: int,
        suggested_source_quality: str,
    ) -> list[str]:
        notes = []

        if detected_text_column:
            notes.append(f"Detected text column: {detected_text_column}")
        else:
            notes.append("No text column detected. Adapter may need updating before ingestion.")

        if detected_rating_column:
            notes.append(f"Detected rating column: {detected_rating_column}")

        if detected_date_column:
            notes.append(f"Detected date column: {detected_date_column}")

        if detected_product_column:
            notes.append(f"Detected product column: {detected_product_column}")

        if detected_vendor_column:
            notes.append(f"Detected vendor column: {detected_vendor_column}")

        if empty_text_rows > 0:
            notes.append(f"Found {empty_text_rows} rows with empty text.")

        if row_count == 0:
            notes.append("Dataset has no data rows.")

        notes.append(f"Suggested source quality: {suggested_source_quality}")

        return notes
