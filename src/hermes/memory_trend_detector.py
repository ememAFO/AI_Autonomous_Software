import json
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from src.research.source_quality import SourceQualityClassifier
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
    top_source_qualities: list[tuple[str, int]]
    average_score: float
    weighted_average_score: float
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
        self.source_quality_classifier = SourceQualityClassifier()

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

            if self._is_non_actionable_positive_feedback(record.pain_point):
                continue
            theme = self._theme_key(record.pain_point)
            grouped_records[theme].append(record)

        themes: list[OpportunityTheme] = []

        for theme, theme_records in grouped_records.items():
            industries = Counter(record.industry for record in theme_records)
            recommendations = Counter(record.recommendation for record in theme_records)
            sources = Counter(record.source for record in theme_records)

            source_qualities = Counter(
                self.source_quality_classifier.classify(
                    source=record.source,
                    industry=record.industry,
                    report_path=record.report_path,
                    pain_point=record.pain_point,
                ).source_quality
                for record in theme_records
            )

            weighted_scores = [
                record.score
                * self.source_quality_classifier.classify(
                    source=record.source,
                    industry=record.industry,
                    report_path=record.report_path,
                    pain_point=record.pain_point,
                ).evidence_weight
                for record in theme_records
            ]

            average_score = round(
                sum(record.score for record in theme_records) / len(theme_records),
                2,
            )

            weighted_average_score = round(
                sum(weighted_scores) / len(weighted_scores),
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
                    top_source_qualities=source_qualities.most_common(5),
                    weighted_average_score=weighted_average_score,
                    average_score=average_score,
                    example_pain_point=theme_records[0].pain_point,
                    report_paths=report_paths[:10],
                )
            )

        return sorted(
            themes,
            key=lambda item: (
                item.record_count,
                item.weighted_average_score,
                item.average_score,
            ),
            reverse=True,
        )

    def _theme_key(self, pain_point: str) -> str:
        text = pain_point.lower()

        has_follow_up = "follow up" in text or "follow-up" in text

        if ("lead" in text or "leads" in text) and has_follow_up:
            return "lead + follow up"

        if ("quote" in text or "quotes" in text) and has_follow_up:
            return "quote + follow up"

        integration_subtheme = self._integration_subtheme(text)

        if integration_subtheme:
            return integration_subtheme

        if self._contains_pricing_pain(text):
            return "pricing + roi"

        if self._contains_capability_expectation_gap(text):
            return "capability expectation gap"

        if self._contains_support_resolution_pain(text):
            return "support resolution"

        if self._contains_support_automation_pain(text):
            return "support automation failure"

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

    def _is_non_actionable_positive_feedback(self, pain_point: str) -> bool:
        text = pain_point.lower().strip()

        positive_no_pain_phrases = {
            "nothing",
            "nothing really",
            "nothing as such",
            "nothing as such for now",
            "no issues",
            "no issue",
            "no problems",
            "no problem",
            "no complaints",
            "no complaint",
            "everything is fine",
            "everything works",
            "works great",
            "works well",
            "amazing and responsive",
            "customer support is amazing",
            "i am completely happy",
            "i'm completely happy",
            "i cannot really say i dislike anything",
            "i can't really say i dislike anything",
            "i dont really dislike anything",
            "i don't really dislike anything",
            "i dislike nothing",
            "best app ever",
        }

        if any(phrase in text for phrase in positive_no_pain_phrases):
            has_actionable_contrast = any(
                phrase in text
                for phrase in {
                    "however",
                    "but",
                    "although",
                    "except",
                    "besides",
                    "only issue",
                    "only problem",
                    "downside",
                    "wish",
                    "could improve",
                    "needs improvement",
                }
            )

            if not has_actionable_contrast:
                return True

        starts_positive_no_pain = any(
            text.startswith(phrase)
            for phrase in {
                "nothing!",
                "nothing.",
                "nothing really",
                "nothing as such",
                "no issues",
                "no problems",
                "i am completely happy",
                "i'm completely happy",
            }
        )

        has_clear_pain_signal = any(
            term in text
            for term in {
                "expensive",
                "difficult",
                "hard to",
                "confusing",
                "bug",
                "bugs",
                "error",
                "errors",
                "fail",
                "fails",
                "failed",
                "limited",
                "manual",
                "missing",
                "not supported",
                "slow",
                "unresolved",
                "poor",
                "awful",
                "terrible",
                "break",
                "breaks",
                "broken",
                "can't",
                "cannot",
                "doesn't work",
                "does not work",
            }
        )

        future_hypothetical_no_pain = any(
            phrase in text
            for phrase in {
                "if any issues arises",
                "if any issues arise",
                "if any issue arises",
                "if any issue arise",
                "in future if any issues",
                "in the future if any issues",
                "will inform",
                "will update",
                "no issues for now",
                "nothing as such for now",
                "nothing for now",
            }
        )

        if future_hypothetical_no_pain and not has_clear_pain_signal:
            return True

        return starts_positive_no_pain and not has_clear_pain_signal

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
    def _integration_subtheme(self, text: str) -> str | None:
        if not self._contains_integration_pain(text):
            return None

        if self._contains_support_access_gap(text):
            return "support access gap"

        if self._contains_support_resolution_pain(text):
            return "support resolution"

        if self._contains_support_automation_pain(text):
            return "support automation failure"

        if self._contains_workflow_backup_recovery_pain(text):
            return "workflow backup and recovery"

        if self._contains_workflow_observability_debugging_pain(text):
            return "workflow observability and debugging"

        if self._contains_pricing_tier_integration_limits(text):
            return "pricing-tier integration limits"

        if self._contains_automation_setup_complexity(text):
            return "automation setup complexity"

        if self._contains_automation_limits_and_task_caps(text):
            return "automation limits and task caps"

        if self._contains_manual_workflow_maintenance(text):
            return "manual workflow maintenance"

        if self._contains_integration_coverage_gap(text):
            return "integration coverage gap"

        if self._contains_integration_reliability_failure(text):
            return "integration reliability failure"

        return "integration workflow"

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

    def _contains_workflow_backup_recovery_pain(self, text: str) -> bool:
        has_backup_language = any(
            term in text
            for term in {
                "backup",
                "back up",
                "download",
                "upload",
                "restore",
                "recovery",
                "recover",
                "version history",
                "rollback",
                "roll back",
                "protected",
                "unprotected",
                "business-critical",
                "business critical",
            }
        )

        has_workflow_language = any(
            term in text
            for term in {
                "zap",
                "zaps",
                "workflow",
                "workflows",
                "automation",
                "automations",
                "process",
                "processes",
            }
        )

        return has_backup_language and has_workflow_language

    def _contains_workflow_observability_debugging_pain(self, text: str) -> bool:
        has_debug_language = any(
            term in text
            for term in {
                "troubleshoot",
                "troubleshooting",
                "debug",
                "debugging",
                "logs",
                "log",
                "audit",
                "history",
                "not obvious",
                "obvious reason",
                "without reason",
                "why it failed",
                "why they fail",
                "error message",
                "error messages",
                "notified of error",
                "monitor",
                "monitoring",
                "alert",
                "alerts",
            }
        )

        has_workflow_language = any(
            term in text
            for term in {
                "zap",
                "zaps",
                "workflow",
                "workflows",
                "automation",
                "automations",
                "integration",
                "integrations",
                "task",
                "tasks",
            }
        )

        return has_debug_language and has_workflow_language

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
                "connection",
                "connections",
                "third party",
                "third-party",
                "api",
                "zap",
                "zaps",
                "automation",
                "automations",
                "workflow",
                "workflows",
            }
        )

    def _contains_support_access_gap(self, text: str) -> bool:
        has_support_channel_language = any(
            term in text
            for term in {
                "live chat",
                "chat support",
                "phone support",
                "email support",
                "support channel",
                "support channels",
                "no live chat",
                "no chat support",
                "no phone support",
                "human support",
                "real person",
                "representative",
            }
        )

        has_access_gap_language = any(
            term in text
            for term in {
                "no ",
                "missing",
                "lack",
                "lacks",
                "without",
                "wish",
                "would be beneficial",
                "need",
                "needs",
                "should have",
                "could use",
            }
        )

        return has_support_channel_language and has_access_gap_language

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


    def _contains_pricing_tier_integration_limits(self, text: str) -> bool:
        has_pricing_language = any(
            term in text
            for term in {
                "premium",
                "paid plan",
                "pricing tier",
                "tier",
                "subscription",
                "free plan",
                "freemium",
                "over my pricing tier",
                "pay",
                "paid",
                "expensive",
                "cost",
                "price",
            }
        )

        has_integration_language = any(
            term in text
            for term in {
                "integration",
                "integrations",
                "connect",
                "connection",
                "connections",
                "zap",
                "zaps",
                "apps",
                "app",
                "task",
                "tasks",
            }
        )

        return has_pricing_language and has_integration_language

    def _contains_integration_reliability_failure(self, text: str) -> bool:
        has_failure_language = any(
            term in text
            for term in {
                "break",
                "breaks",
                "broken",
                "fail",
                "fails",
                "failed",
                "failure",
                "not working",
                "doesn't work",
                "does not work",
                "error",
                "errors",
                "glitch",
                "glitches",
                "reconnect",
                "reconnecting",
                "disconnect",
                "disconnected",
                "troubleshoot",
                "troubleshooting",
                "not obvious reason",
            }
        )

        has_integration_language = any(
            term in text
            for term in {
                "integration",
                "integrations",
                "connect",
                "connection",
                "connections",
                "sync",
                "zap",
                "zaps",
                "automation",
                "automations",
            }
        )

        return has_failure_language and has_integration_language

    def _contains_automation_setup_complexity(self, text: str) -> bool:
        has_complexity_language = any(
            term in text
            for term in {
                "complicated",
                "complex",
                "complexity",
                "challenging",
                "difficult",
                "hard to",
                "tough",
                "confusing",
                "trial and error",
                "setup",
                "set up",
                "setting up",
                "figure out",
                "learning",
                "learn",
                "coding",
                "configure",
                "configuration",
                "formulas",
                "field instructions",
            }
        )

        has_automation_language = any(
            term in text
            for term in {
                "zap",
                "zaps",
                "workflow",
                "workflows",
                "automation",
                "automations",
                "trigger",
                "triggers",
                "action",
                "actions",
                "integration",
                "integrations",
            }
        )

        return has_complexity_language and has_automation_language

    def _contains_automation_limits_and_task_caps(self, text: str) -> bool:
        has_limit_language = any(
            term in text
            for term in {
                "limited",
                "limitations",
                "limit",
                "limits",
                "too simple",
                "not supported",
                "unsupported",
                "no if-then",
                "if-then",
                "looping",
                "multiple triggers",
                "single action",
                "number of tasks",
                "task limit",
                "task limits",
                "tasks included",
                "task cap",
                "task caps",
                "workflow task limit",
                "workflow task limits",
                "block automation",
                "blocks automation",
                "paths",
                "more tasks",
                "more actions",
                "more triggers",
                "functionality",
            }
        )

        has_automation_language = any(
            term in text
            for term in {
                "zap",
                "zaps",
                "workflow",
                "workflows",
                "automation",
                "automations",
                "trigger",
                "triggers",
                "action",
                "actions",
                "task",
                "tasks",
            }
        )

        return has_limit_language and has_automation_language

    def _contains_manual_workflow_maintenance(self, text: str) -> bool:
        has_manual_language = any(
            term in text
            for term in {
                "manual",
                "manually",
                "manual fixing",
                "fixing",
                "editing",
                "edit",
                "maintain",
                "maintenance",
                "backup",
                "download",
                "upload",
                "rework",
                "workaround",
                "work around",
            }
        )

        has_workflow_language = any(
            term in text
            for term in {
                "zap",
                "zaps",
                "workflow",
                "workflows",
                "automation",
                "automations",
                "contract",
                "contracts",
                "document",
                "documents",
            }
        )

        return has_manual_language and has_workflow_language

    def _contains_integration_coverage_gap(self, text: str) -> bool:
        has_gap_language = any(
            term in text
            for term in {
                "not available",
                "missing",
                "not on",
                "not supported",
                "unsupported",
                "wish there were more",
                "more apps",
                "more integrations",
                "official whatsapp",
                "relevant to my industry",
                "cannot integrate",
                "can't integrate",
                "cant integrate",
                "intergrate",
                "zoho",
                "wpforms",
                "salesforce",
            }
        )

        has_integration_language = any(
            term in text
            for term in {
                "integration",
                "integrations",
                "connect",
                "connected",
                "connection",
                "apps",
                "app",
                "software",
                "platforms",
                "zap",
                "zaps",
            }
        )

        return has_gap_language and has_integration_language

    def _validate_memory_dir(self, memory_dir: Path) -> Path:
        resolved = memory_dir.resolve()
        project_root = Path.cwd().resolve()
        allowed_root = (project_root / "data" / "hermes" / "research_memory").resolve()

        if not str(resolved).startswith(str(allowed_root)):
            raise MemoryTrendDetectorError(
                "Memory trend detector can only read inside data/hermes/research_memory"
            )

        return resolved
