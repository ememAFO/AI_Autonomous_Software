import pytest

from src.research.industry_taxonomy import IndustryCategory
from src.research.research_planner import ResearchPlanner, ResearchPlannerError
from src.research.source_catalog import SourceType


def test_research_planner_creates_sales_plan():
    planner = ResearchPlanner()

    plan = planner.plan_for_industry(IndustryCategory.SALES)

    assert plan.industry == IndustryCategory.SALES
    assert plan.suggested_queries
    assert "sales follow up" in plan.suggested_queries

    source_types = {source.source_type for source in plan.recommended_sources}

    assert SourceType.REDDIT in source_types
    assert SourceType.PRODUCT_HUNT in source_types
    assert SourceType.G2 in source_types


def test_research_planner_creates_saas_plan():
    planner = ResearchPlanner()

    plan = planner.plan_for_industry(IndustryCategory.SAAS)

    assert plan.industry == IndustryCategory.SAAS
    assert "Product Hunt launch" in plan.suggested_queries

    source_types = {source.source_type for source in plan.recommended_sources}

    assert SourceType.PRODUCT_HUNT in source_types
    assert SourceType.GITHUB_ISSUES in source_types


def test_research_planner_parses_industry_from_text():
    planner = ResearchPlanner()

    plan = planner.plan_from_text("real-estate")

    assert plan.industry == IndustryCategory.REAL_ESTATE


def test_research_planner_blocks_empty_industry_text():
    planner = ResearchPlanner()

    with pytest.raises(ResearchPlannerError):
        planner.plan_from_text("")


def test_research_planner_blocks_unknown_industry():
    planner = ResearchPlanner()

    with pytest.raises(ResearchPlannerError):
        planner.plan_from_text("unknown industry")


def test_research_planner_includes_blocked_sources_for_accountability():
    planner = ResearchPlanner()

    plan = planner.plan_for_industry(IndustryCategory.SALES)

    assert plan.blocked_sources
    assert any(source.allowed is False for source in plan.blocked_sources)


def test_research_planner_limits_queries_and_sources():
    planner = ResearchPlanner()

    plan = planner.plan_for_industry(IndustryCategory.SALES)

    assert len(plan.suggested_queries) <= planner.MAX_QUERIES
    assert len(plan.recommended_sources) <= planner.MAX_SOURCES
