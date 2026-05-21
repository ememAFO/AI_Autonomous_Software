import pytest

from src.workflows.engine import WorkflowEngine, WorkflowError, WorkflowStage


def test_workflow_progression_is_sequential():
    engine = WorkflowEngine()
    assert engine.current_stage == WorkflowStage.RESEARCH
    assert engine.next_stage(True) == WorkflowStage.VALIDATION
    assert engine.next_stage(True) == WorkflowStage.PLANNING


def test_workflow_blocks_failed_stage():
    engine = WorkflowEngine()
    with pytest.raises(WorkflowError):
        engine.next_stage(False, "Research failed")
    assert engine.current_stage == WorkflowStage.RESEARCH


def test_workflow_assert_stage_blocks_stage_skipping():
    engine = WorkflowEngine()
    with pytest.raises(WorkflowError):
        engine.assert_stage(WorkflowStage.TESTING)
