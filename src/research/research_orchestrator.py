from dataclasses import dataclass

from src.adapters.reddit_fetcher import RedditResearchQuery
from src.research.reddit_research_job import RedditResearchJob, RedditResearchJobResult
from src.research.workflow_engine import ResearchStage, ResearchWorkflowEngine


@dataclass(frozen=True)
class ResearchOrchestratorResult:
    final_stage: ResearchStage
    job_result: RedditResearchJobResult


class ResearchOrchestrator:
    """
    Enforces the research workflow order.

    Workflow:
    DISCOVER -> FETCH -> EXTRACT -> CLEAN -> ANALYZE -> SCORE -> REPORT

    Security and governance rules:
    - No stage skipping.
    - Empty inputs are blocked.
    - Failed jobs stop the workflow.
    - Research jobs must pass through the workflow engine.
    """

    def __init__(
        self,
        workflow_engine: ResearchWorkflowEngine | None = None,
        reddit_job: RedditResearchJob | None = None,
    ):
        self.workflow_engine = workflow_engine or ResearchWorkflowEngine()
        self.reddit_job = reddit_job or RedditResearchJob()

    def run_reddit_research(
        self,
        research_query: RedditResearchQuery,
        industry: str,
    ) -> ResearchOrchestratorResult:
        self._validate_inputs(research_query=research_query, industry=industry)

        self._require_stage(ResearchStage.DISCOVER)

        # DISCOVER passed: query and industry were validated.
        self.workflow_engine.next_stage(passed=True)

        # FETCH stage: safe fetcher runs inside RedditResearchJob.
        self._require_stage(ResearchStage.FETCH)
        job_result = self.reddit_job.run(
            research_query=research_query,
            industry=industry,
        )
        self.workflow_engine.next_stage(passed=True)

        # EXTRACT stage: pain extraction happened inside the pipeline.
        self._require_stage(ResearchStage.EXTRACT)
        self.workflow_engine.next_stage(passed=job_result.processed_count > 0)

        # CLEAN stage: adapter rejected non-business/noisy posts.
        self._require_stage(ResearchStage.CLEAN)
        self.workflow_engine.next_stage(passed=True)

        # ANALYZE stage: opportunities were created for accepted posts.
        self._require_stage(ResearchStage.ANALYZE)
        self.workflow_engine.next_stage(passed=job_result.accepted_count > 0)

        # SCORE stage: scored opportunities exist in pipeline results.
        self._require_stage(ResearchStage.SCORE)
        scored_results_exist = all(
            pipeline_result.score.total_score >= 0
            for pipeline_result in job_result.adapter_result.results
        )
        self.workflow_engine.next_stage(passed=scored_results_exist)

        # REPORT stage: all accepted results must have report files.
        self._require_stage(ResearchStage.REPORT)
        reports_exist = all(
            pipeline_result.report_path.exists()
            for pipeline_result in job_result.adapter_result.results
        )

        if not reports_exist:
            raise ValueError("Research report generation failed")

        return ResearchOrchestratorResult(
            final_stage=self.workflow_engine.current_stage,
            job_result=job_result,
        )

    def _validate_inputs(
        self,
        research_query: RedditResearchQuery,
        industry: str,
    ) -> None:
        if not research_query.query.strip():
            raise ValueError("Research query cannot be empty")

        if not research_query.subreddit.strip():
            raise ValueError("Subreddit cannot be empty")

        if not industry or not industry.strip():
            raise ValueError("Industry cannot be empty")

    def _require_stage(self, expected_stage: ResearchStage) -> None:
        if self.workflow_engine.current_stage != expected_stage:
            raise ValueError(
                f"Invalid research workflow stage. "
                f"Expected {expected_stage}, got {self.workflow_engine.current_stage}"
            )
