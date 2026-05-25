from dataclasses import dataclass, field
from pathlib import Path

from src.adapters.reddit_fetcher import RedditFetcherError
from src.hermes.research_memory_sync import HermesResearchMemorySync
from src.research.reddit_job_planner import (
    PlannedRedditResearchJob,
    RedditJobPlan,
    RedditJobPlanner,
    RedditJobPlannerError,
)
from src.research.research_orchestrator import ResearchOrchestrator
from src.research.run_manifest import ResearchRunManifestWriter
from src.research.run_registry import ResearchRunRegistryWriter


@dataclass(frozen=True)
class PlannedRedditJobRunResult:
    planned_job: PlannedRedditResearchJob
    status: str
    processed_count: int = 0
    accepted_count: int = 0
    rejected_count: int = 0
    final_workflow_stage: str | None = None
    report_paths: list[str] = field(default_factory=list)
    manifest_path: str | None = None
    registry_path: str | None = None
    hermes_memory_count: int = 0
    hermes_memory_paths: list[str] = field(default_factory=list)
    error: str | None = None


@dataclass(frozen=True)
class PlannedRedditResearchBatchResult:
    industry: str
    planned_count: int
    successful_count: int
    blocked_count: int
    results: list[PlannedRedditJobRunResult]


class PlannedRedditResearchRunner:
    """
    Runs planned Reddit research jobs through the controlled research system.

    Security rules:
    - Jobs must come from RedditJobPlanner.
    - Each job goes through ResearchOrchestrator.
    - Each successful job creates manifest, registry entry, Hermes memory records.
    - Failed jobs are blocked and recorded, not retried endlessly.
    - No live scraping is introduced here.
    """

    def __init__(
        self,
        job_planner: RedditJobPlanner | None = None,
        orchestrator: ResearchOrchestrator | None = None,
        manifest_writer: ResearchRunManifestWriter | None = None,
        registry_writer: ResearchRunRegistryWriter | None = None,
        memory_sync: HermesResearchMemorySync | None = None,
    ):
        self.job_planner = job_planner or RedditJobPlanner()
        self.orchestrator = orchestrator or ResearchOrchestrator()
        self.manifest_writer = manifest_writer or ResearchRunManifestWriter()
        self.registry_writer = registry_writer or ResearchRunRegistryWriter()
        self.memory_sync = memory_sync or HermesResearchMemorySync()

    def run_for_industry(
        self,
        industry_text: str,
        limit_per_job: int = 5,
    ) -> PlannedRedditResearchBatchResult:
        try:
            plan = self.job_planner.plan_from_text(
                industry_text=industry_text,
                limit_per_job=limit_per_job,
            )
        except RedditJobPlannerError:
            raise

        return self.run_plan(plan)

    def run_plan(
        self,
        plan: RedditJobPlan,
    ) -> PlannedRedditResearchBatchResult:
        results: list[PlannedRedditJobRunResult] = []

        for planned_job in plan.jobs:
            result = self._run_single_job(planned_job)
            results.append(result)

        successful_count = sum(1 for result in results if result.status == "success")
        blocked_count = sum(1 for result in results if result.status == "blocked")

        return PlannedRedditResearchBatchResult(
            industry=plan.industry.value,
            planned_count=len(plan.jobs),
            successful_count=successful_count,
            blocked_count=blocked_count,
            results=results,
        )

    def _run_single_job(
        self,
        planned_job: PlannedRedditResearchJob,
    ) -> PlannedRedditJobRunResult:
        try:
            self.orchestrator.workflow_engine.reset()
            orchestrator_result = self.orchestrator.run_reddit_research(
                research_query=planned_job.query,
                industry=planned_job.industry.value,
            )

            job_result = orchestrator_result.job_result

            report_paths = [
                str(pipeline_result.report_path)
                for pipeline_result in job_result.adapter_result.results
            ]

            memory_sync_result = self.memory_sync.sync_from_reddit_job(job_result)
            memory_paths = [
                str(memory_path)
                for memory_path in memory_sync_result.memory_paths
            ]

            manifest = self.manifest_writer.create_manifest(
                status="success",
                query=job_result.query.query,
                subreddit=job_result.query.subreddit,
                industry=planned_job.industry.value,
                final_workflow_stage=orchestrator_result.final_stage.value,
                processed_count=job_result.processed_count,
                accepted_count=job_result.accepted_count,
                rejected_count=job_result.rejected_count,
                report_paths=report_paths,
                hermes_memory_count=memory_sync_result.written_count,
                hermes_memory_paths=memory_paths,
            )

            manifest_path = self.manifest_writer.write(manifest)

            registry_path = self.registry_writer.add_run(
                manifest=manifest,
                manifest_path=str(manifest_path),
            )

            return PlannedRedditJobRunResult(
                planned_job=planned_job,
                status="success",
                processed_count=job_result.processed_count,
                accepted_count=job_result.accepted_count,
                rejected_count=job_result.rejected_count,
                final_workflow_stage=orchestrator_result.final_stage.value,
                report_paths=report_paths,
                manifest_path=str(manifest_path),
                registry_path=str(registry_path),
                hermes_memory_count=memory_sync_result.written_count,
                hermes_memory_paths=memory_paths,
            )

        except (ValueError, RedditFetcherError, RedditJobPlannerError) as exc:
            return PlannedRedditJobRunResult(
                planned_job=planned_job,
                status="blocked",
                error=str(exc),
            )
