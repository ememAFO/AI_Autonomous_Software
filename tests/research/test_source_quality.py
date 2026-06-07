from src.research.source_quality import SourceQualityClassifier


def test_source_quality_classifier_marks_g2_as_core_evidence():
    result = SourceQualityClassifier().classify(
        source="g2_reviews",
        industry="saas",
        report_path="reports/opportunities/integration_workflow_pain.md",
        pain_point="Zapier integrations are hard to configure.",
    )

    assert result.source_quality == "core_evidence"
    assert result.evidence_weight == 1.0


def test_source_quality_classifier_marks_issue_tracker_as_core_issue_evidence():
    result = SourceQualityClassifier().classify(
        source="issue_tracker",
        industry="developer_tools",
        report_path="reports/opportunities/bug_report_pain.md",
        pain_point="GitHub issue requests a feature for workflow debugging.",
    )

    assert result.source_quality == "core_evidence_issue_tracker"
    assert result.evidence_weight == 1.0


def test_source_quality_classifier_marks_app_store_business_apps_as_supporting():
    result = SourceQualityClassifier().classify(
        source="app_store",
        industry="saas",
        report_path="reports/opportunities/product_usability_friction.md",
        pain_point="Business app has confusing onboarding.",
    )

    assert result.source_quality == "supporting_evidence"
    assert result.evidence_weight == 0.75


def test_source_quality_classifier_marks_trustpilot_airline_as_operational():
    result = SourceQualityClassifier().classify(
        source="trustpilot_reviews",
        industry="airline",
        report_path="reports/opportunities/support_resolution_pain.md",
        pain_point="Customer support delays caused unresolved service problems.",
    )

    assert result.source_quality == "operational_evidence"
    assert result.evidence_weight == 0.6


def test_source_quality_classifier_marks_reddit_as_research_or_synthetic():
    result = SourceQualityClassifier().classify(
        source="reddit",
        industry="sales",
        report_path="reports/opportunities/lead_follow-up_automation.md",
        pain_point="Sales teams lose leads because manual follow up is slow.",
    )

    assert result.source_quality == "research_or_synthetic_evidence"
    assert result.evidence_weight == 0.5


def test_source_quality_classifier_marks_netflix_as_exploratory():
    result = SourceQualityClassifier().classify(
        source="app_store",
        industry="saas",
        report_path="reports/opportunities/content_access_friction.md",
        pain_point="Netflix removed movies and users cannot access shows.",
    )

    assert result.source_quality == "exploratory_evidence"
    assert result.evidence_weight == 0.35
