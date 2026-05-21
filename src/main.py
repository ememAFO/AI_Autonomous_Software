from src.workflows.engine import WorkflowEngine
from src.policy_engine.engine import PolicyEngine
from src.policy_engine.models import DeploymentContext
from src.utils.reporting import ReportWriter


def main() -> None:
    engine = WorkflowEngine()
    reporter = ReportWriter()
    policy = PolicyEngine()

    reporter.write_report(
        category="daily",
        filename="daily_report.md",
        title="Daily Opportunity Report",
        summary="Factory initialized in restricted mode.",
        risks=["No real research connectors configured yet."],
        next_actions=["Run research stage", "Validate one opportunity", "Keep deployment blocked"],
    )

    deployment_decision = policy.validate_deployment(
        DeploymentContext(
            tests_passed=False,
            security_scan_passed=False,
            dependency_scan_passed=False,
            protected_files_changed=False,
            human_approval_present=False,
            auth_or_billing_modified=False,
            deployment_proposal_present=False,
            target_environment="production",
        )
    )

    print(f"Starting workflow at: {engine.current_stage}")
    print(f"Production deployment allowed: {deployment_decision.allowed}")


if __name__ == "__main__":
    main()
