import pytest

from src.approvals.gate import ApprovalGate, ApprovalRequest


def test_approval_required_before_sensitive_action():
    gate = ApprovalGate()
    gate.request(ApprovalRequest(
        request_id="deploy-1",
        stage="WAITING_APPROVAL",
        summary="Deploy to staging",
        requested_by="agent-zero",
    ))

    with pytest.raises(PermissionError):
        gate.assert_approved("deploy-1")

    gate.approve("deploy-1", approver="human-owner")
    gate.assert_approved("deploy-1")
