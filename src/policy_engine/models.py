from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class PolicyDecision:
    allowed: bool
    reasons: list[str] = field(default_factory=list)

    def require_allowed(self) -> None:
        if not self.allowed:
            joined = "; ".join(self.reasons) or "Policy denied action."
            raise PermissionError(joined)


@dataclass(frozen=True)
class DeploymentContext:
    tests_passed: bool
    security_scan_passed: bool
    dependency_scan_passed: bool
    protected_files_changed: bool
    human_approval_present: bool
    auth_or_billing_modified: bool
    deployment_proposal_present: bool
    target_environment: str


@dataclass(frozen=True)
class AgentActionContext:
    actor: str
    action: str
    target_path: str | None = None
    requires_network: bool = False
    modifies_auth_or_billing: bool = False
    touches_production_secret: bool = False
    escalates_privilege: bool = False
