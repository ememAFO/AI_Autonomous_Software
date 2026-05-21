from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum


class ApprovalStatus(str, Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


@dataclass
class ApprovalRequest:
    request_id: str
    stage: str
    summary: str
    requested_by: str
    status: ApprovalStatus = ApprovalStatus.PENDING
    approved_by: str | None = None
    created_at: str = datetime.now(timezone.utc).isoformat()


class ApprovalGate:
    """Human approval gate. Production/staging deployment must check this explicitly."""

    def __init__(self) -> None:
        self._requests: dict[str, ApprovalRequest] = {}

    def request(self, request: ApprovalRequest) -> ApprovalRequest:
        self._requests[request.request_id] = request
        return request

    def approve(self, request_id: str, approver: str) -> ApprovalRequest:
        request = self._requests[request_id]
        request.status = ApprovalStatus.APPROVED
        request.approved_by = approver
        return request

    def reject(self, request_id: str, approver: str) -> ApprovalRequest:
        request = self._requests[request_id]
        request.status = ApprovalStatus.REJECTED
        request.approved_by = approver
        return request

    def assert_approved(self, request_id: str) -> None:
        request = self._requests.get(request_id)
        if request is None or request.status != ApprovalStatus.APPROVED:
            raise PermissionError("Human approval is missing or not approved")
