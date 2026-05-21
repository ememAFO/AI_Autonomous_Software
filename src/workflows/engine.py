from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from pathlib import Path


class WorkflowStage(StrEnum):
    RESEARCH = "RESEARCH"
    VALIDATION = "VALIDATION"
    PLANNING = "PLANNING"
    BUILDING = "BUILDING"
    TESTING = "TESTING"
    SECURITY_REVIEW = "SECURITY_REVIEW"
    POLICY_REVIEW = "POLICY_REVIEW"
    WAITING_APPROVAL = "WAITING_APPROVAL"
    DEPLOYMENT = "DEPLOYMENT"


WORKFLOW_STAGES: list[WorkflowStage] = [
    WorkflowStage.RESEARCH,
    WorkflowStage.VALIDATION,
    WorkflowStage.PLANNING,
    WorkflowStage.BUILDING,
    WorkflowStage.TESTING,
    WorkflowStage.SECURITY_REVIEW,
    WorkflowStage.POLICY_REVIEW,
    WorkflowStage.WAITING_APPROVAL,
    WorkflowStage.DEPLOYMENT,
]


class WorkflowError(Exception):
    """Raised when a workflow action violates the approved sequence."""


@dataclass(frozen=True)
class StageRecord:
    stage: WorkflowStage
    passed: bool
    summary: str
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class WorkflowEngine:
    """Strict sequential workflow engine.

    This engine fails closed: a failed stage raises an error and blocks progression.
    The engine does not deploy anything; it only controls state progression.
    """

    def __init__(self, report_dir: Path | str = "reports") -> None:
        self.current_stage = WORKFLOW_STAGES[0]
        self.history: list[StageRecord] = []
        self.report_dir = Path(report_dir)

    def next_stage(self, passed: bool, summary: str = "") -> WorkflowStage:
        if not passed:
            self.history.append(StageRecord(self.current_stage, False, summary or "Stage failed."))
            raise WorkflowError(f"Workflow failed at stage: {self.current_stage}")

        self.history.append(StageRecord(self.current_stage, True, summary or "Stage passed."))
        current_index = WORKFLOW_STAGES.index(self.current_stage)

        if current_index < len(WORKFLOW_STAGES) - 1:
            self.current_stage = WORKFLOW_STAGES[current_index + 1]

        return self.current_stage

    def assert_stage(self, expected_stage: WorkflowStage) -> None:
        if self.current_stage != expected_stage:
            raise WorkflowError(
                f"Invalid workflow stage. Expected {expected_stage}, got {self.current_stage}."
            )

    def reset_to_research(self) -> None:
        self.current_stage = WorkflowStage.RESEARCH
        self.history.append(StageRecord(WorkflowStage.RESEARCH, False, "Workflow restarted."))
