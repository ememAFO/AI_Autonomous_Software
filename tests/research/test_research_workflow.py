import pytest

from src.research.workflow_engine import (
    ResearchStage,
    ResearchWorkflowEngine,
    ResearchWorkflowError,
)


def test_research_workflow_starts_at_discover():
    engine = ResearchWorkflowEngine()

    assert engine.current_stage == ResearchStage.DISCOVER


def test_research_workflow_moves_to_next_stage_when_passed():
    engine = ResearchWorkflowEngine()

    next_stage = engine.next_stage(passed=True)

    assert next_stage == ResearchStage.FETCH


def test_research_workflow_blocks_when_stage_fails():
    engine = ResearchWorkflowEngine()

    with pytest.raises(ResearchWorkflowError):
        engine.next_stage(passed=False)


def test_research_workflow_can_reset():
    engine = ResearchWorkflowEngine()

    engine.next_stage(passed=True)
    engine.reset()

    assert engine.current_stage == ResearchStage.DISCOVER
