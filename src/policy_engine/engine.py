from __future__ import annotations

from pathlib import Path

from src.security.permissions import PermissionError as FactoryPermissionError, PermissionPolicy
from src.utils.audit_log import AuditLogger
from .models import AgentActionContext, DeploymentContext, PolicyDecision


PROTECTED_PATHS = ("protected/",)
BLOCKED_KEYWORDS = (
    "STRIPE_SECRET_KEY=sk_live",
    "DEBUG=true",
    "DEBUG=True",
    "LIVE_DEPLOYMENT=true",
    "LIVE_DEPLOYMENT=True",
    "-----BEGIN PRIVATE KEY-----",
)


class PolicyEngine:
    """Central fail-closed policy engine for the AI software factory."""

    def __init__(self, repo_root: Path | str = ".", audit_logger: AuditLogger | None = None) -> None:
        self.repo_root = Path(repo_root).resolve()
        self.permissions = PermissionPolicy(self.repo_root)
        self.audit = audit_logger or AuditLogger(self.repo_root / "logs" / "audit.jsonl")

    def _decision(self, allowed: bool, reasons: list[str], *, actor: str = "system", action: str = "policy_check") -> PolicyDecision:
        self.audit.record(
            event_type="policy_decision",
            actor=actor,
            action=action,
            outcome="allowed" if allowed else "blocked",
            details={"reasons": reasons},
        )
        return PolicyDecision(allowed, reasons)

    def check_file_change(self, relative_path: str) -> PolicyDecision:
        try:
            self.permissions.assert_edit_allowed(relative_path)
            return self._decision(True, [], action="check_file_change")
        except FactoryPermissionError as exc:
            return self._decision(False, [str(exc)], action="check_file_change")

    def check_agent_action(self, context: AgentActionContext) -> PolicyDecision:
        reasons: list[str] = []
        if context.target_path:
            file_decision = self.check_file_change(context.target_path)
            reasons.extend(file_decision.reasons)
        if context.modifies_auth_or_billing:
            reasons.append("Auth or billing modification requires explicit human approval.")
        if context.touches_production_secret:
            reasons.append("Production secrets are never available to agents.")
        if context.escalates_privilege:
            reasons.append("Privilege escalation is blocked.")
        if context.action.lower() in {"deploy_production", "modify_governance", "issue_refund"}:
            reasons.append(f"Action is blocked by governance: {context.action}")
        return self._decision(not reasons, reasons, actor=context.actor, action=context.action)

    def scan_for_insecure_defaults(self, text: str) -> PolicyDecision:
        reasons = [f"Blocked insecure value found: {keyword}" for keyword in BLOCKED_KEYWORDS if keyword in text]
        return self._decision(not reasons, reasons, action="scan_for_insecure_defaults")

    def validate_deployment(self, context: DeploymentContext) -> PolicyDecision:
        reasons: list[str] = []

        if context.target_environment.lower() == "production":
            reasons.append("Production deployment is blocked by default. Use human release process.")
        if not context.tests_passed:
            reasons.append("Tests have not passed.")
        if not context.security_scan_passed:
            reasons.append("Security scan has not passed.")
        if not context.dependency_scan_passed:
            reasons.append("Dependency scan has not passed.")
        if context.protected_files_changed:
            reasons.append("Protected files were modified.")
        if not context.human_approval_present:
            reasons.append("Human approval is missing.")
        if context.auth_or_billing_modified:
            reasons.append("Auth or billing modifications require explicit approval.")
        if not context.deployment_proposal_present:
            reasons.append("Deployment proposal is missing.")

        return self._decision(not reasons, reasons, action="validate_deployment")
