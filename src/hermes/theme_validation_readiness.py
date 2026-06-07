from dataclasses import dataclass

from src.hermes.memory_trend_detector import OpportunityTheme


@dataclass(frozen=True)
class ThemeValidationReadiness:
    theme: str
    readiness: str
    readiness_score: float
    reason: str
    recommended_next_action: str
    risk_flags: list[str]


class ThemeValidationReadinessEvaluator:
    """
    Evaluates whether a repeated opportunity theme is ready for market validation.

    This layer does NOT approve building.
    It only ranks themes for validation readiness.

    Possible readiness labels:
    - VALIDATION_READY
    - WATCH
    - INSUFFICIENT_EVIDENCE
    - DO_NOT_PRIORITIZE
    """

    MIN_VALIDATION_READY_RECORDS = 15
    MIN_VALIDATION_READY_WEIGHTED_SCORE = 6.0
    MIN_WATCH_RECORDS = 8
    MIN_WATCH_WEIGHTED_SCORE = 4.5

    def evaluate(self, theme: OpportunityTheme) -> ThemeValidationReadiness:
        score = self._readiness_score(theme)
        risk_flags = self._risk_flags(theme)

        if "exploratory_only_evidence" in risk_flags:
            return ThemeValidationReadiness(
                theme=theme.theme,
                readiness="DO_NOT_PRIORITIZE",
                readiness_score=score,
                reason="Theme is based only on exploratory evidence and should not drive SaaS validation decisions.",
                recommended_next_action="Keep for traceability, but do not prioritize for validation.",
                risk_flags=risk_flags,
            )

        if (
            theme.record_count >= self.MIN_VALIDATION_READY_RECORDS
            and theme.weighted_average_score >= self.MIN_VALIDATION_READY_WEIGHTED_SCORE
            and self._has_meaningful_validate_mix(theme)
            and not self._has_dominant_reject_mix(theme)
        ):
            return ThemeValidationReadiness(
                theme=theme.theme,
                readiness="VALIDATION_READY",
                readiness_score=score,
                reason="Theme has repeated evidence, acceptable weighted score, and enough validation-oriented signals.",
                recommended_next_action="Create a lightweight validation plan before any MVP build.",
                risk_flags=risk_flags,
            )

        if (
            theme.record_count >= self.MIN_WATCH_RECORDS
            and theme.weighted_average_score >= self.MIN_WATCH_WEIGHTED_SCORE
        ):
            return ThemeValidationReadiness(
                theme=theme.theme,
                readiness="WATCH",
                readiness_score=score,
                reason="Theme has repeated signals but is not strong enough for validation-ready status yet.",
                recommended_next_action="Collect more core evidence and review rejected examples for false positives.",
                risk_flags=risk_flags,
            )

        return ThemeValidationReadiness(
            theme=theme.theme,
            readiness="INSUFFICIENT_EVIDENCE",
            readiness_score=score,
            reason="Theme does not yet have enough weighted evidence for validation.",
            recommended_next_action="Do not prioritize yet. Continue collecting evidence.",
            risk_flags=risk_flags,
        )

    def evaluate_many(
        self,
        themes: list[OpportunityTheme],
    ) -> list[ThemeValidationReadiness]:
        results = [self.evaluate(theme) for theme in themes]

        readiness_rank = {
            "VALIDATION_READY": 4,
            "WATCH": 3,
            "INSUFFICIENT_EVIDENCE": 2,
            "DO_NOT_PRIORITIZE": 1,
        }

        return sorted(
            results,
            key=lambda item: (
                readiness_rank.get(item.readiness, 0),
                item.readiness_score,
            ),
            reverse=True,
        )

    def _readiness_score(self, theme: OpportunityTheme) -> float:
        count_score = min(theme.record_count / 50, 1.0) * 30
        weighted_score = min(theme.weighted_average_score / 10, 1.0) * 35
        source_quality_score = self._source_quality_score(theme) * 20
        recommendation_score = self._recommendation_score(theme) * 15

        return round(
            count_score
            + weighted_score
            + source_quality_score
            + recommendation_score,
            2,
        )

    def _source_quality_score(self, theme: OpportunityTheme) -> float:
        total = sum(count for _, count in theme.top_source_qualities)

        if total == 0:
            return 0.0

        weights = {
            "core_evidence": 1.0,
            "core_evidence_issue_tracker": 1.0,
            "supporting_evidence": 0.75,
            "operational_evidence": 0.6,
            "research_or_synthetic_evidence": 0.5,
            "unknown_evidence": 0.4,
            "exploratory_evidence": 0.35,
        }

        weighted_total = sum(
            count * weights.get(quality, 0.4)
            for quality, count in theme.top_source_qualities
        )

        return weighted_total / total

    def _recommendation_score(self, theme: OpportunityTheme) -> float:
        total = sum(count for _, count in theme.top_recommendations)

        if total == 0:
            return 0.0

        weights = {
            "BUILD_NOW": 1.0,
            "VALIDATE_FIRST": 0.8,
            "WATCH": 0.45,
            "REJECT": 0.0,
        }

        weighted_total = sum(
            count * weights.get(recommendation, 0.0)
            for recommendation, count in theme.top_recommendations
        )

        return weighted_total / total

    def _has_meaningful_validate_mix(self, theme: OpportunityTheme) -> bool:
        recommendation_counts = dict(theme.top_recommendations)
        validate_count = recommendation_counts.get("VALIDATE_FIRST", 0)
        build_count = recommendation_counts.get("BUILD_NOW", 0)

        return (validate_count + build_count) >= max(3, theme.record_count * 0.4)

    def _has_dominant_reject_mix(self, theme: OpportunityTheme) -> bool:
        recommendation_counts = dict(theme.top_recommendations)
        reject_count = recommendation_counts.get("REJECT", 0)

        return reject_count > theme.record_count * 0.5

    def _risk_flags(self, theme: OpportunityTheme) -> list[str]:
        flags = []

        quality_counts = dict(theme.top_source_qualities)
        recommendation_counts = dict(theme.top_recommendations)

        if quality_counts and set(quality_counts) == {"exploratory_evidence"}:
            flags.append("exploratory_only_evidence")

        if recommendation_counts.get("REJECT", 0) > theme.record_count * 0.5:
            flags.append("reject_dominant_theme")

        if theme.weighted_average_score < theme.average_score:
            flags.append("weighted_score_lower_than_raw_score")

        if theme.record_count < self.MIN_WATCH_RECORDS:
            flags.append("low_record_count")

        if theme.weighted_average_score < self.MIN_WATCH_WEIGHTED_SCORE:
            flags.append("low_weighted_score")

        if "integration workflow" == theme.theme:
            flags.append("broad_theme_needs_further_subclassification")

        return flags
