from src.policy_engine.engine import PolicyEngine
from src.policy_engine.models import DeploymentContext


def test_protected_file_change_is_blocked():
    policy = PolicyEngine()
    decision = policy.check_file_change("protected/WORKFLOW_RULES.md")
    assert decision.allowed is False
    assert "Protected file" in decision.reasons[0]


def test_normal_source_file_change_is_allowed():
    policy = PolicyEngine()
    decision = policy.check_file_change("src/workflows/engine.py")
    assert decision.allowed is True


def test_production_deployment_is_blocked_even_with_checks():
    policy = PolicyEngine()
    decision = policy.validate_deployment(
        DeploymentContext(
            tests_passed=True,
            security_scan_passed=True,
            dependency_scan_passed=True,
            protected_files_changed=False,
            human_approval_present=True,
            auth_or_billing_modified=False,
            deployment_proposal_present=True,
            target_environment="production",
        )
    )
    assert decision.allowed is False
    assert any("Production deployment" in reason for reason in decision.reasons)


def test_staging_deployment_requires_all_checks():
    policy = PolicyEngine()
    decision = policy.validate_deployment(
        DeploymentContext(
            tests_passed=True,
            security_scan_passed=True,
            dependency_scan_passed=True,
            protected_files_changed=False,
            human_approval_present=True,
            auth_or_billing_modified=False,
            deployment_proposal_present=True,
            target_environment="staging",
        )
    )
    assert decision.allowed is True


def test_insecure_defaults_are_blocked():
    policy = PolicyEngine()
    decision = policy.scan_for_insecure_defaults("DEBUG=true\n")
    assert decision.allowed is False
