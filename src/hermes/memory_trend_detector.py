import json
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from src.hermes.research_memory import HermesResearchMemoryRecord


class MemoryTrendDetectorError(Exception):
    pass


@dataclass(frozen=True)
class OpportunityTheme:
    theme: str
    record_count: int
    top_industries: list[tuple[str, int]]
    top_recommendations: list[tuple[str, int]]
    average_score: float
    example_pain_point: str
    report_paths: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class MemoryTrendSummary:
    total_records: int
    top_industries: list[tuple[str, int]]
    top_recommendations: list[tuple[str, int]]
    repeated_pain_terms: list[tuple[str, int]]
    high_confidence_records: list[HermesResearchMemoryRecord] = field(default_factory=list)
    high_confidence_themes: list[OpportunityTheme] = field(default_factory=list)


class HermesMemoryTrendDetector:
    """
    Reads local Hermes research memory records and summarizes repeated opportunity patterns.

    Purpose:
    - detect repeated pain themes
    - identify high-confidence opportunity themes
    - summarize industries and recommendations
    - support product intelligence without giving Hermes execution authority

    Security rules:
    - Reads only from data/hermes/research_memory
    - Reads JSON files only
    - Ignores malformed records
    - Does not execute file content
    """

    DEFAULT_MEMORY_DIR = Path("data/hermes/research_memory")

    PAIN_KEYWORDS = [
        "lead",
        "leads",
        "follow up",
        "follow-up",
        "quote",
        "quotes",
        "booking",
        "bookings",
        "appointment",
        "appointments",
        "invoice",
        "invoices",
        "crm",
        "manual",
        "reminder",
        "reminders",
        "customer",
        "customers",
        "client",
        "clients",
        "revenue",
        "sales",
        "support",
        "integration",
        "onboarding",
    ]

    THEME_KEYWORDS = [
        "lead",
        "follow up",
        "follow-up",
        "quote",
        "booking",
        "appointment",
        "invoice",
        "crm",
        "integration",
        "onboarding",
        "support",
        "manual",
        "reminder",
    ]

    def __init__(self, memory_dir: str | Path = DEFAULT_MEMORY_DIR):
        self.memory_dir = self._validate_memory_dir(Path(memory_dir))

    def summarize(self) -> MemoryTrendSummary:
        records = self._load_records()

        industry_counter = Counter(record.industry for record in records)
        recommendation_counter = Counter(record.recommendation for record in records)
        pain_counter = self._count_pain_terms(records)

        high_confidence_records = [
            record for record in records if record.score >= 8
        ]

        high_confidence_themes = self._build_opportunity_themes(
            high_confidence_records
        )

        return MemoryTrendSummary(
            total_records=len(records),
            top_industries=industry_counter.most_common(10),
            top_recommendations=recommendation_counter.most_common(10),
            repeated_pain_terms=pain_counter.most_common(15),
            high_confidence_records=high_confidence_records[:20],
            high_confidence_themes=high_confidence_themes[:20],
        )

    def _load_records(self) -> list[HermesResearchMemoryRecord]:
        if not self.memory_dir.exists():
            return []

        records: list[HermesResearchMemoryRecord] = []

        for path in sorted(self.memory_dir.glob("*.json")):
            try:
                raw_data = json.loads(path.read_text(encoding="utf-8"))
                records.append(self._record_from_dict(raw_data))
            except (json.JSONDecodeError, TypeError, KeyError, ValueError):
                continue

        return records

    def _record_from_dict(self, data: dict[str, Any]) -> HermesResearchMemoryRecord:
        return HermesResearchMemoryRecord(
            source=str(data["source"]),
            industry=str(data["industry"]),
            pain_point=str(data["pain_point"]),
            recommendation=str(data["recommendation"]),
            score=float(data["score"]),
            report_path=str(data["report_path"]),
            timestamp=str(data["timestamp"]),
        )

    def _count_pain_terms(
        self,
        records: list[HermesResearchMemoryRecord],
    ) -> Counter[str]:
        counter: Counter[str] = Counter()

        for record in records:
            text = record.pain_point.lower()

            for keyword in self.PAIN_KEYWORDS:
                if keyword in text:
                    counter[keyword] += 1

        return counter

    def _build_opportunity_themes(
        self,
        records: list[HermesResearchMemoryRecord],
    ) -> list[OpportunityTheme]:
        grouped_records: dict[str, list[HermesResearchMemoryRecord]] = defaultdict(list)

        for record in records:
            theme = self._theme_key(record.pain_point)
            grouped_records[theme].append(record)

        themes: list[OpportunityTheme] = []

        for theme, theme_records in grouped_records.items():
            industries = Counter(record.industry for record in theme_records)
            recommendations = Counter(record.recommendation for record in theme_records)
            average_score = round(
                sum(record.score for record in theme_records) / len(theme_records),
                2,
            )

            report_paths = list(
                dict.fromkeys(record.report_path for record in theme_records)
            )

            themes.append(
                OpportunityTheme(
                    theme=theme,
                    record_count=len(theme_records),
                    top_industries=industries.most_common(5),
                    top_recommendations=recommendations.most_common(5),
                    average_score=average_score,
                    example_pain_point=theme_records[0].pain_point,
                    report_paths=report_paths[:10],
                )
            )

        return sorted(
            themes,
            key=lambda item: (item.record_count, item.average_score),
            reverse=True,
        )

    def _theme_key(self, pain_point: str) -> str:
        text = pain_point.lower()

        has_follow_up = "follow up" in text or "follow-up" in text

        if ("lead" in text or "leads" in text) and has_follow_up:
            return "lead + follow up"

        if ("quote" in text or "quotes" in text) and has_follow_up:
            return "quote + follow up"

        if ("booking" in text or "bookings" in text or "appointment" in text or "appointments" in text) and (
            "reminder" in text or "reminders" in text or "missed" in text
        ):
            return "booking + reminders"

        if "crm" in text and ("manual" in text or "data entry" in text):
            return "crm + manual admin"

        if "integration" in text or "integrations" in text:
            return "integration gap"

        if "onboarding" in text:
            return "onboarding"

        matched_keywords = [
            keyword.replace("-", " ")
            for keyword in self.THEME_KEYWORDS
            if keyword in text
        ]

        if matched_keywords:
            return " + ".join(dict.fromkeys(matched_keywords[:4]))

        words = [
            word.strip(".,!?;:()[]{}").lower()
            for word in text.split()
        ]

        meaningful_words = [
            word
            for word in words
            if len(word) >= 5
        ]

        return " ".join(meaningful_words[:5]) or "uncategorized"

    def _validate_memory_dir(self, memory_dir: Path) -> Path:
        resolved = memory_dir.resolve()
        project_root = Path.cwd().resolve()
        allowed_root = (project_root / "data" / "hermes" / "research_memory").resolve()

        if not str(resolved).startswith(str(allowed_root)):
            raise MemoryTrendDetectorError(
                "Memory trend detector can only read inside data/hermes/research_memory"
            )

        return resolved
