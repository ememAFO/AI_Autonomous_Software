from enum import StrEnum


class ResearchWorkflowError(Exception):
    pass


class ResearchStage(StrEnum):
    DISCOVER = "DISCOVER"
    FETCH = "FETCH"
    EXTRACT = "EXTRACT"
    CLEAN = "CLEAN"
    ANALYZE = "ANALYZE"
    SCORE = "SCORE"
    REPORT = "REPORT"


RESEARCH_STAGES = [
    ResearchStage.DISCOVER,
    ResearchStage.FETCH,
    ResearchStage.EXTRACT,
    ResearchStage.CLEAN,
    ResearchStage.ANALYZE,
    ResearchStage.SCORE,
    ResearchStage.REPORT,
]


class ResearchWorkflowEngine:
    def __init__(self):
        self.current_stage = ResearchStage.DISCOVER

    def next_stage(self, passed: bool) -> ResearchStage:
        if not passed:
            raise ResearchWorkflowError(
                f"Research workflow failed at stage: {self.current_stage}"
            )

        current_index = RESEARCH_STAGES.index(self.current_stage)

        if current_index < len(RESEARCH_STAGES) - 1:
            self.current_stage = RESEARCH_STAGES[current_index + 1]

        return self.current_stage

    def reset(self) -> None:
        self.current_stage = ResearchStage.DISCOVER
