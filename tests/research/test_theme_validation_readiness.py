from src.hermes.memory_trend_detector import OpportunityTheme
from src.hermes.theme_validation_readiness import (
    ThemeValidationReadinessEvaluator,
)


def make_theme(
    *,
    theme: str = "lead + follow up",
    record_count: int = 20,
    average_score: float = 6.5,
    weighted_average_score: float = 6.5,
    top_source_qualities: list[tuple[str, int]] | None = None,
    top_recommendations: list[tuple[str, int]] | None = None,
) -> OpportunityTheme:
    return OpportunityTheme(
        theme=theme,
        record_count=record_count,
        top_industries=[("saas", record_count)],
        top_recommendations=top_recommendations or [("VALIDATE_FIRST", record_count)],
        top_sources=[("review_site", record_count)],
        top_source_qualities=top_source_qualities or [("core_evidence", record_count)],
        average_score=average_score,
        weighted_average_score=weighted_average_score,
        example_pain_point="Manual CRM follow up is slow and sales teams lose leads.",
        report_paths=["reports/opportunities/lead_follow-up_automation.md"],
    )


def test_theme_validation_readiness_marks_strong_theme_as_validation_ready():
    theme = make_theme(
        record_count=20,
        weighted_average_score=6.5,
        top_source_qualities=[("core_evidence", 20)],
        top_recommendations=[("VALIDATE_FIRST", 18), ("WATCH", 2)],
    )

    result = ThemeValidationReadinessEvaluator().evaluate(theme)

    assert result.readiness == "VALIDATION_READY"
    assert result.readiness_score > 0
    assert result.theme == "lead + follow up"


def test_theme_validation_readiness_marks_repeated_but_weaker_theme_as_watch():
    theme = make_theme(
        theme="automation setup complexity",
        record_count=79,
        average_score=5.37,
        weighted_average_score=4.97,
        top_source_qualities=[("core_evidence", 59), ("supporting_evidence", 20)],
        top_recommendations=[("REJECT", 39), ("VALIDATE_FIRST", 32), ("WATCH", 8)],
    )

    result = ThemeValidationReadinessEvaluator().evaluate(theme)

    assert result.readiness == "WATCH"
    assert "reject_dominant_theme" not in result.risk_flags


def test_theme_validation_readiness_does_not_prioritize_exploratory_only_theme():
    theme = make_theme(
        theme="content access friction",
        record_count=14,
        average_score=6.0,
        weighted_average_score=2.1,
        top_source_qualities=[("exploratory_evidence", 14)],
        top_recommendations=[("VALIDATE_FIRST", 6), ("REJECT", 4), ("WATCH", 4)],
    )

    result = ThemeValidationReadinessEvaluator().evaluate(theme)

    assert result.readiness == "DO_NOT_PRIORITIZE"
    assert "exploratory_only_evidence" in result.risk_flags


def test_theme_validation_readiness_marks_small_theme_as_insufficient():
    theme = make_theme(
        theme="small weak theme",
        record_count=3,
        average_score=5.0,
        weighted_average_score=4.0,
        top_source_qualities=[("core_evidence", 3)],
        top_recommendations=[("WATCH", 3)],
    )

    result = ThemeValidationReadinessEvaluator().evaluate(theme)

    assert result.readiness == "INSUFFICIENT_EVIDENCE"
    assert "low_record_count" in result.risk_flags


def test_theme_validation_readiness_sorts_many_results_by_readiness():
    evaluator = ThemeValidationReadinessEvaluator()

    results = evaluator.evaluate_many(
        [
            make_theme(
                theme="content access friction",
                record_count=14,
                weighted_average_score=2.1,
                top_source_qualities=[("exploratory_evidence", 14)],
            ),
            make_theme(
                theme="lead + follow up",
                record_count=20,
                weighted_average_score=6.5,
                top_source_qualities=[("core_evidence", 20)],
                top_recommendations=[("VALIDATE_FIRST", 18), ("WATCH", 2)],
            ),
        ]
    )

    assert results[0].readiness == "VALIDATION_READY"
    assert results[-1].readiness == "DO_NOT_PRIORITIZE"
