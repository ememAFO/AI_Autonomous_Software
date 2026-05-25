import json
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from src.hermes.research_memory import HermesResearchMemoryRecord


class MemoryTrendDetectorError(Exception):
    pass


@dataclass(frozen=True)
class MemoryTrendSummary:
    total_records: int
    top_industries: list[tuple[str, int]]
    top_recommendations: list[tuple[str, int]]
    repeated_pain_terms: list[tuple[str, int]]
    high_confidence_records: list[HermesResearchMemoryRecord] = field(default_factory=list)


class HermesMemoryTrendDetector:
    """
    Reads local Hermes research memory records and summarizes repeated opportunity patterns.

    Purpose:
    - detect repeated pain themes
    - identify high-confidence opportunities
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

        return MemoryTrendSummary(
            total_records=len(records),
            top_industries=industry_counter.most_common(10),
            top_recommendations=recommendation_counter.most_common(10),
            repeated_pain_terms=pain_counter.most_common(15),
            high_confidence_records=high_confidence_records[:20],
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

    def _validate_memory_dir(self, memory_dir: Path) -> Path:
        resolved = memory_dir.resolve()
        project_root = Path.cwd().resolve()
        allowed_root = (project_root / "data" / "hermes" / "research_memory").resolve()

        if not str(resolved).startswith(str(allowed_root)):
            raise MemoryTrendDetectorError(
                "Memory trend detector can only read inside data/hermes/research_memory"
            )

        return resolved
