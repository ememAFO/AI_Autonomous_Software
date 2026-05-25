from src.research.industry_taxonomy import (
    IndustryCategory,
    IndustryTaxonomy,
)


def test_industry_taxonomy_includes_sales_and_saas():
    taxonomy = IndustryTaxonomy()

    categories = taxonomy.list_categories()

    assert IndustryCategory.SALES in categories
    assert IndustryCategory.SAAS in categories


def test_sales_profile_contains_sales_pain_themes():
    taxonomy = IndustryTaxonomy()

    profile = taxonomy.get(IndustryCategory.SALES)

    assert "CRM data entry" in profile.pain_themes
    assert "AI sales follow-up assistant" in profile.example_opportunities


def test_saas_profile_supports_new_product_research():
    taxonomy = IndustryTaxonomy()

    profile = taxonomy.get(IndustryCategory.SAAS)

    assert "new product discovery" in profile.pain_themes
    assert "Product Hunt launch" in profile.research_keywords


def test_taxonomy_search_finds_accounting_from_invoice_keyword():
    taxonomy = IndustryTaxonomy()

    matches = taxonomy.search_by_keyword("invoice")

    categories = [profile.category for profile in matches]

    assert IndustryCategory.ACCOUNTING in categories
