import json
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from src.hermes.research_memory import HermesResearchMemoryRecord


class MemoryTrendDetectorError(Exception):
    pass


@dataclass(frozen=True)
class MemoryTrendFilter:
    industry: str | None = None
    source: str | None = None
    exclude_source: str | None = None
    recommendation: str | None = None


@dataclass(frozen=True)
class OpportunityTheme:
    theme: str
    record_count: int
    top_industries: list[tuple[str, int]]
    top_recommendations: list[tuple[str, int]]
    top_sources: list[tuple[str, int]]
    average_score: float
    example_pain_point: str
    report_paths: list[str] = field(default_factory=list)

@dataclass(frozen=True)
class MemoryTrendSummary:
    total_records: int
    filtered_records: int
    filters: MemoryTrendFilter
    top_industries: list[tuple[str, int]]
    top_sources: list[tuple[str, int]]
    top_recommendations: list[tuple[str, int]]
    repeated_pain_terms: list[tuple[str, int]]
    filtered_themes: list[OpportunityTheme] = field(default_factory=list)
    high_confidence_records: list[HermesResearchMemoryRecord] = field(default_factory=list)
    high_confidence_themes: list[OpportunityTheme] = field(default_factory=list)


class HermesMemoryTrendDetector:
    """
    Reads local Hermes research memory records and summarizes repeated opportunity patterns.

    Purpose:
    - detect repeated pain themes
    - identify high-confidence opportunity themes
    - summarize industries, sources, and recommendations
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
        "pricing",
        "paywall",
        "paywalls",
        "expensive",
        "duplicate",
        "duplicates",
        "delayed",
        "delay",
        "cancelled",
        "canceled",
        "refund",
        "training",
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
        "pricing",
        "paywall",
        "paywalls",
        "expensive",
        "duplicate",
        "duplicates",
        "delay",
        "delayed",
        "cancelled",
        "canceled",
        "refund",
        "training",
    ]

    def __init__(self, memory_dir: str | Path = DEFAULT_MEMORY_DIR):
        self.memory_dir = self._validate_memory_dir(Path(memory_dir))

    def summarize(
        self,
        filters: MemoryTrendFilter | None = None,
    ) -> MemoryTrendSummary:
        filters = filters or MemoryTrendFilter()

        all_records = self._load_records()
        records = self._apply_filters(all_records, filters)

        industry_counter = Counter(record.industry for record in records)
        source_counter = Counter(record.source for record in records)
        recommendation_counter = Counter(record.recommendation for record in records)
        pain_counter = self._count_pain_terms(records)
        filtered_themes = self._build_opportunity_themes(records)

        high_confidence_records = [record for record in records if record.score >= 8]

        high_confidence_themes = self._build_opportunity_themes(high_confidence_records)




        return MemoryTrendSummary(
            total_records=len(all_records),
            filtered_records=len(records),
            filters=filters,
            top_industries=industry_counter.most_common(10),
            top_sources=source_counter.most_common(10),
            top_recommendations=recommendation_counter.most_common(10),
            repeated_pain_terms=pain_counter.most_common(15),
            filtered_themes=filtered_themes[:20],
            high_confidence_records=high_confidence_records[:20],
            high_confidence_themes=high_confidence_themes[:20],
        )

    def _apply_filters(
        self,
        records: list[HermesResearchMemoryRecord],
        filters: MemoryTrendFilter,
    ) -> list[HermesResearchMemoryRecord]:
        filtered = records

        if filters.industry:
            expected = filters.industry.lower()
            filtered = [
                record for record in filtered
                if record.industry.lower() == expected
            ]

        if filters.source:
            expected = filters.source.lower()
            filtered = [
                record for record in filtered
                if record.source.lower() == expected
            ]

        if filters.exclude_source:
            excluded = filters.exclude_source.lower()
            filtered = [
                record for record in filtered
                if record.source.lower() != excluded
            ]

        if filters.recommendation:
            expected = filters.recommendation.lower()
            filtered = [
                record for record in filtered
                if record.recommendation.lower() == expected
            ]

        return filtered

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
            sources = Counter(record.source for record in theme_records)

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
                    top_sources=sources.most_common(5),
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

        if self._contains_pricing_pain(text):
            return "pricing + roi"

        if self._contains_capability_expectation_gap(text):
            return "capability expectation gap"

        if self._contains_support_resolution_pain(text):
            return "support resolution"

        if self._contains_support_automation_pain(text):
            return "support automation failure"

        if self._contains_integration_pain(text):
            return "integration workflow"

        if self._contains_onboarding_pain(text):
            return "onboarding + training"

        if self._contains_delay_cancellation_pain(text):
            return "delay + cancellation"

        if self._contains_content_access_pain(text):
            return "content access friction"

        if self._contains_product_usability_pain(text):
            return "product usability friction"

        if self._contains_booking_reminder_pain(text):
            return "booking + reminders"

        if "crm" in text and ("manual" in text or "data entry" in text):
            return "crm + manual admin"

        if "refund" in text:
            return "refund + resolution"

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

        stop_words = {
            "about",
            "after",
            "again",
            "because",
            "being",
            "could",
            "every",
            "having",
            "hubspot",
            "marketing",
            "netflix",
            "platform",
            "product",
            "really",
            "review",
            "their",
            "there",
            "these",
            "those",
            "thing",
            "things",
            "through",
            "united",
            "using",
            "while",
            "would",
        }

        meaningful_words = [
            word
            for word in words
            if len(word) >= 5 and word not in stop_words
        ]

        return " ".join(meaningful_words[:5]) or "uncategorized"

    def _contains_pricing_pain(self, text: str) -> bool:
        return any(
            term in text
            for term in {
                "pricing",
                "price",
                "prices",
                "expensive",
                "cost",
                "costly",
                "paywall",
                "paywalls",
                "overpay",
                "overpaying",
                "subscription",
                "billing",
                "charged",
            }
        )

    def _contains_support_resolution_pain(self, text: str) -> bool:
        has_support = (
            "support" in text
            or "customer service" in text
            or "call center" in text
            or "callcentre" in text
            or "agent" in text
            or "representative" in text
        )

        has_resolution_problem = any(
            term in text
            for term in {
                "slow",
                "unresolved",
                "not resolved",
                "resolve",
                "escalated",
                "escalation",
                "can't reach",
                "cannot reach",
                "never reach",
                "no call",
                "wait",
                "waiting",
                "less helpful",
            }
        )

        return has_support and has_resolution_problem

    def _contains_support_automation_pain(self, text: str) -> bool:
        has_automation = (
            "chatbot" in text
            or "bot" in text
            or "automated" in text
            or "automation" in text
        )

        has_failure = any(
            term in text
            for term in {
                "doesn't work",
                "does not work",
                "not work",
                "failed",
                "failure",
                "half the time",
                "can't get connected",
                "cannot get connected",
                "wait",
                "waiting",
            }
        )

        return has_automation and has_failure

    def _contains_integration_pain(self, text: str) -> bool:
        return any(
            term in text
            for term in {
                "integration",
                "integrations",
                "duplicate contact",
                "duplicate contacts",
                "duplicate",
                "duplicates",
                "sync",
                "synchronization",
                "connected",
                "connect",
                "third party",
                "third-party",
                "api",
            }
        )

    def _contains_onboarding_pain(self, text: str) -> bool:
        return any(
            term in text
            for term in {
                "onboarding",
                "training",
                "learning curve",
                "hard to learn",
                "setup",
                "set up",
                "configure",
                "configuration",
                "difficult to learn",
                "not intuitive",
            }
        )

    def _contains_delay_cancellation_pain(self, text: str) -> bool:
        return any(
            term in text
            for term in {
                "delay",
                "delayed",
                "cancelled",
                "canceled",
                "cancellation",
                "cancelation",
                "late",
                "waiting",
                "waited",
                "rescheduled",
            }
        )

    def _contains_content_access_pain(self, text: str) -> bool:
        has_content_or_access = any(
            term in text
            for term in {
                "content",
                "movie",
                "movies",
                "show",
                "shows",
                "watch",
                "streaming",
                "wifi",
                "household",
                "households",
                "password",
                "access",
                "account",
            }
        )

        has_policy_or_loss = any(
            term in text
            for term in {
                "remove",
                "removed",
                "lose",
                "losing",
                "lost",
                "cannot",
                "can't",
                "unable",
                "not able",
                "change",
                "updates",
                "policy",
                "different wifi",
            }
        )

        return has_content_or_access and has_policy_or_loss

    def _contains_product_usability_pain(self, text: str) -> bool:
        return any(
            term in text
            for term in {
                "confusing",
                "hard to use",
                "difficult",
                "clunky",
                "bug",
                "bugs",
                "errors",
                "error",
                "doesn't work",
                "does not work",
                "not working",
                "poor interface",
                "limited flexibility",
                "limited",
                "quality",
                "low quality",
            }
        )

    def _contains_booking_reminder_pain(self, text: str) -> bool:
        has_booking = any(
            term in text
            for term in {
                "booking",
                "bookings",
                "appointment",
                "appointments",
            }
        )

        has_reminder = any(
            term in text
            for term in {
                "reminder",
                "reminders",
                "missed",
                "no show",
                "no-show",
            }
        )

        return has_booking and has_reminder

    def _contains_capability_expectation_gap(self, text: str) -> bool:
        has_expectation_language = any(
            term in text
            for term in {
                "lied to",
                "overpromised",
                "over promised",
                "not as advertised",
                "capabilities",
                "capability",
                "features promised",
                "was told",
                "expected",
                "expectation",
                "does not match",
                "doesn't match",
            }
        )

        has_product_gap_language = any(
            term in text
            for term in {
                "limited",
                "missing",
                "not available",
                "cannot",
                "can't",
                "does not",
                "doesn't",
                "hard to",
                "difficult",
                "expansive tool",
                "capabilities",
            }
        )

        return has_expectation_language and has_product_gap_language

    def _validate_memory_dir(self, memory_dir: Path) -> Path:
        resolved = memory_dir.resolve()
        project_root = Path.cwd().resolve()
        allowed_root = (project_root / "data" / "hermes" / "research_memory").resolve()

        if not str(resolved).startswith(str(allowed_root)):
            raise MemoryTrendDetectorError(
                "Memory trend detector can only read inside data/hermes/research_memory"
            )

        return resolved
