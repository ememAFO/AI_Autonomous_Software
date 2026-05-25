from src.research.industry_taxonomy import IndustryCategory
from src.research.source_catalog import SourceCatalog, SourceType


def test_source_catalog_has_allowed_sources():
    catalog = SourceCatalog()

    allowed_sources = catalog.allowed_sources()

    assert allowed_sources
    assert all(source.allowed for source in allowed_sources)


def test_source_catalog_has_sales_sources():
    catalog = SourceCatalog()

    sources = catalog.sources_for_industry(IndustryCategory.SALES)

    source_types = {source.source_type for source in sources}

    assert SourceType.REDDIT in source_types
    assert SourceType.PRODUCT_HUNT in source_types
    assert SourceType.G2 in source_types


def test_source_catalog_has_saas_launch_sources():
    catalog = SourceCatalog()

    sources = catalog.sources_for_industry(IndustryCategory.SAAS)

    source_types = {source.source_type for source in sources}

    assert SourceType.PRODUCT_HUNT in source_types
    assert SourceType.GITHUB_ISSUES in source_types


def test_source_catalog_blocks_private_support_forums():
    catalog = SourceCatalog()

    support_forums = catalog.sources_for_type(SourceType.SUPPORT_FORUM)

    assert support_forums
    assert support_forums[0].allowed is False
    assert support_forums[0].blocked_reason is not None


def test_source_catalog_limits_results_per_run():
    catalog = SourceCatalog()

    for source in catalog.allowed_sources():
        assert source.max_results_per_run <= 25
