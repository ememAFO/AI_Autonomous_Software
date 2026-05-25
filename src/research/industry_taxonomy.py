from dataclasses import dataclass, field
from enum import StrEnum


class IndustryCategory(StrEnum):
    SALES = "sales"
    MARKETING = "marketing"
    SAAS = "saas"
    HEALTHCARE = "healthcare"
    CLINICS = "clinics"
    HOME_SERVICES = "home services"
    REAL_ESTATE = "real estate"
    ACCOUNTING = "accounting"
    RECRUITMENT = "recruitment"
    EDUCATION = "education"
    HOSPITALITY = "hospitality"
    ECOMMERCE = "e-commerce"
    LEGAL = "legal"
    CONSTRUCTION = "construction"
    FITNESS = "fitness"
    CREATOR_ECONOMY = "creator economy"
    CUSTOMER_SUPPORT = "customer support"
    AGENCIES = "agencies"


@dataclass(frozen=True)
class IndustryProfile:
    category: IndustryCategory
    description: str
    pain_themes: list[str] = field(default_factory=list)
    research_keywords: list[str] = field(default_factory=list)
    example_opportunities: list[str] = field(default_factory=list)


class IndustryTaxonomy:
    """
    Controlled industry map for opportunity research.

    Purpose:
    - keep research focused
    - avoid random browsing
    - make industry expansion structured
    - support sales, SaaS, healthcare, accounting, real estate, and other sectors
    """

    def __init__(self):
        self._profiles = self._build_profiles()

    def get(self, category: IndustryCategory) -> IndustryProfile:
        return self._profiles[category]

    def list_categories(self) -> list[IndustryCategory]:
        return list(self._profiles.keys())

    def search_by_keyword(self, keyword: str) -> list[IndustryProfile]:
        if not keyword or not keyword.strip():
            return []

        normalized_keyword = keyword.lower().strip()

        matches: list[IndustryProfile] = []

        for profile in self._profiles.values():
            searchable_text = " ".join(
                [
                    profile.category.value,
                    profile.description,
                    *profile.pain_themes,
                    *profile.research_keywords,
                    *profile.example_opportunities,
                ]
            ).lower()

            if normalized_keyword in searchable_text:
                matches.append(profile)

        return matches

    def _build_profiles(self) -> dict[IndustryCategory, IndustryProfile]:
        return {
            IndustryCategory.SALES: IndustryProfile(
                category=IndustryCategory.SALES,
                description="Sales teams, account executives, business development teams, and lead generation workflows.",
                pain_themes=[
                    "manual lead follow-up",
                    "CRM data entry",
                    "missed demos",
                    "proposal follow-up",
                    "pipeline visibility",
                    "cold outreach tracking",
                    "sales call notes",
                    "lost deals",
                ],
                research_keywords=[
                    "sales follow up",
                    "CRM is annoying",
                    "lead tracking",
                    "missed demo",
                    "manual sales reporting",
                    "pipeline management pain",
                ],
                example_opportunities=[
                    "AI sales follow-up assistant",
                    "CRM note summarizer",
                    "proposal follow-up automation",
                    "lead scoring assistant",
                ],
            ),
            IndustryCategory.SAAS: IndustryProfile(
                category=IndustryCategory.SAAS,
                description="Software-as-a-service products, startup tools, AI tools, and new digital products.",
                pain_themes=[
                    "expensive subscriptions",
                    "missing integrations",
                    "poor onboarding",
                    "feature gaps",
                    "slow support",
                    "complex setup",
                    "new product discovery",
                ],
                research_keywords=[
                    "new SaaS tool",
                    "Product Hunt launch",
                    "SaaS alternative",
                    "missing integration",
                    "too expensive SaaS",
                    "AI tool directory",
                ],
                example_opportunities=[
                    "micro SaaS competitor gap tracker",
                    "SaaS onboarding improvement assistant",
                    "AI tool comparison engine",
                    "integration gap finder",
                ],
            ),
            IndustryCategory.HEALTHCARE: IndustryProfile(
                category=IndustryCategory.HEALTHCARE,
                description="Healthcare administration, patient workflows, hospital operations, clinics, and care coordination.",
                pain_themes=[
                    "missed appointments",
                    "patient follow-up",
                    "manual reporting",
                    "admin burden",
                    "document collection",
                    "staff scheduling",
                    "waiting list management",
                ],
                research_keywords=[
                    "missed appointment",
                    "patient follow up",
                    "healthcare admin burden",
                    "clinic workflow",
                    "manual healthcare reporting",
                ],
                example_opportunities=[
                    "patient reminder assistant",
                    "clinic admin automation",
                    "healthcare workflow dashboard",
                    "waiting list follow-up assistant",
                ],
            ),
            IndustryCategory.ACCOUNTING: IndustryProfile(
                category=IndustryCategory.ACCOUNTING,
                description="Accounting firms, bookkeeping, tax preparation, client document collection, and invoice workflows.",
                pain_themes=[
                    "invoice chasing",
                    "receipt collection",
                    "client document reminders",
                    "manual reconciliation",
                    "month-end reporting",
                    "tax document collection",
                ],
                research_keywords=[
                    "invoice chasing",
                    "client documents accounting",
                    "receipt collection",
                    "bookkeeping pain",
                    "manual reconciliation",
                ],
                example_opportunities=[
                    "client document reminder assistant",
                    "invoice chasing automation",
                    "receipt collection workflow",
                    "bookkeeping task tracker",
                ],
            ),
            IndustryCategory.REAL_ESTATE: IndustryProfile(
                category=IndustryCategory.REAL_ESTATE,
                description="Estate agents, landlords, letting agents, property managers, and viewing workflows.",
                pain_themes=[
                    "lead response",
                    "viewing scheduling",
                    "tenant communication",
                    "landlord updates",
                    "property maintenance follow-up",
                    "document collection",
                ],
                research_keywords=[
                    "real estate lead follow up",
                    "viewing scheduling",
                    "tenant communication",
                    "property management pain",
                    "letting agent admin",
                ],
                example_opportunities=[
                    "property lead response assistant",
                    "viewing scheduler",
                    "tenant update assistant",
                    "maintenance follow-up tracker",
                ],
            ),
            IndustryCategory.RECRUITMENT: IndustryProfile(
                category=IndustryCategory.RECRUITMENT,
                description="Recruiters, staffing agencies, HR teams, candidate pipelines, and interview workflows.",
                pain_themes=[
                    "candidate screening",
                    "interview scheduling",
                    "candidate follow-up",
                    "CV sorting",
                    "pipeline tracking",
                    "client updates",
                ],
                research_keywords=[
                    "candidate follow up",
                    "interview scheduling pain",
                    "recruiter admin",
                    "CV screening",
                    "candidate pipeline",
                ],
                example_opportunities=[
                    "candidate follow-up assistant",
                    "interview scheduling automation",
                    "CV shortlisting helper",
                    "recruitment pipeline tracker",
                ],
            ),
            IndustryCategory.HOME_SERVICES: IndustryProfile(
                category=IndustryCategory.HOME_SERVICES,
                description="Cleaners, plumbers, roofers, electricians, decorators, HVAC, and local service businesses.",
                pain_themes=[
                    "missed quotes",
                    "manual follow-up",
                    "missed bookings",
                    "no-shows",
                    "customer reminders",
                    "job scheduling",
                ],
                research_keywords=[
                    "clients stop replying after quotes",
                    "manual follow up",
                    "missed bookings",
                    "home service leads",
                    "roofing quote follow up",
                ],
                example_opportunities=[
                    "AI lead recovery assistant",
                    "quote follow-up automation",
                    "booking reminder assistant",
                    "job scheduling assistant",
                ],
            ),
            IndustryCategory.ECOMMERCE: IndustryProfile(
                category=IndustryCategory.ECOMMERCE,
                description="Online stores, Shopify merchants, marketplace sellers, and direct-to-consumer brands.",
                pain_themes=[
                    "abandoned carts",
                    "returns",
                    "customer support",
                    "inventory alerts",
                    "order tracking",
                    "review collection",
                ],
                research_keywords=[
                    "abandoned cart problem",
                    "Shopify support pain",
                    "returns management",
                    "inventory tracking",
                    "ecommerce customer support",
                ],
                example_opportunities=[
                    "returns automation assistant",
                    "review request assistant",
                    "abandoned cart recovery helper",
                    "inventory alert dashboard",
                ],
            ),
            IndustryCategory.CUSTOMER_SUPPORT: IndustryProfile(
                category=IndustryCategory.CUSTOMER_SUPPORT,
                description="Support teams, help desks, ticket management, customer success, and service operations.",
                pain_themes=[
                    "slow ticket response",
                    "repetitive support questions",
                    "poor handover",
                    "ticket tagging",
                    "customer churn signals",
                    "knowledge base gaps",
                ],
                research_keywords=[
                    "support ticket pain",
                    "customer support automation",
                    "repetitive support questions",
                    "help desk workflow",
                    "ticket tagging",
                ],
                example_opportunities=[
                    "support ticket triage assistant",
                    "knowledge base gap detector",
                    "customer churn signal tracker",
                    "support reply draft assistant",
                ],
            ),
        }
