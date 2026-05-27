from dataclasses import dataclass, field
from pathlib import Path

from src.adapters.local_csv_feedback_adapter import (
    LocalCSVFeedbackAdapter,
    LocalCSVFeedbackAdapterError,
    LocalFeedbackItem,
)
from src.hermes.research_memory import HermesResearchMemoryHook
from src.research.models import OpportunitySource
from src.research.pipeline import PipelineResult, ResearchPipeline
from src.research.run_manifest import ResearchRunManifestWriter
from src.research.run_registry import ResearchRunRegistryWriter
from src.research.feedback_text_cleaner import FeedbackTextCleaner


@dataclass(frozen=True)
class LocalFeedbackResearchItemResult:
    item: LocalFeedbackItem
    status: str
    report_path: str | None = None
    manifest_path: str | None = None
    registry_path: str | None = None
    hermes_memory_path: str | None = None
    error: str | None = None


@dataclass(frozen=True)
class LocalFeedbackResearchRunResult:
    source_path: str
    industry: str
    source_type: str
    loaded_count: int
    processed_count: int
    successful_count: int
    blocked_count: int
    results: list[LocalFeedbackResearchItemResult] = field(default_factory=list)


class LocalFeedbackResearchRunner:
    """
    Runs local CSV feedback through the controlled research pipeline.

    Security rules:
    - CSV loading goes through LocalCSVFeedbackAdapter path checks.
    - Each feedback item goes through ResearchPipeline.
    - Each successful item creates a report, manifest, registry entry, and Hermes memory record.
    - Failed items are blocked and recorded.
    - No external network access is performed.
    """

    def __init__(
        self,
        adapter: LocalCSVFeedbackAdapter | None = None,
        pipeline: ResearchPipeline | None = None,
        manifest_writer: ResearchRunManifestWriter | None = None,
        registry_writer: ResearchRunRegistryWriter | None = None,
        memory_hook: HermesResearchMemoryHook | None = None,
        feedback_text_cleaner: FeedbackTextCleaner | None = None,
    ):
        self.adapter = adapter or LocalCSVFeedbackAdapter()
        self.pipeline = pipeline or ResearchPipeline()
        self.manifest_writer = manifest_writer or ResearchRunManifestWriter()
        self.registry_writer = registry_writer or ResearchRunRegistryWriter()
        self.memory_hook = memory_hook or HermesResearchMemoryHook()
        self.feedback_text_cleaner = feedback_text_cleaner or FeedbackTextCleaner()

    def run_file(
        self,
        csv_path: str | Path,
        *,
        industry: str,
        source_type: str = "local_csv_feedback",
        max_rows: int = 10,
    ) -> LocalFeedbackResearchRunResult:
        try:
            load_result = self.adapter.load_file(
                csv_path,
                industry=industry,
                source_type=source_type,
                max_rows=max_rows,
            )
        except LocalCSVFeedbackAdapterError:
            raise

        results: list[LocalFeedbackResearchItemResult] = []

        for item in load_result.items:
            results.append(self._process_item(item))

        successful_count = sum(1 for result in results if result.status == "success")
        blocked_count = sum(1 for result in results if result.status == "blocked")

        return LocalFeedbackResearchRunResult(
            source_path=str(load_result.source_path),
            industry=industry,
            source_type=source_type,
            loaded_count=load_result.loaded_count,
            processed_count=len(results),
            successful_count=successful_count,
            blocked_count=blocked_count,
            results=results,
        )

    def _process_item(
        self,
        item: LocalFeedbackItem,
    ) -> LocalFeedbackResearchItemResult:
        try:
            pain_text = self.feedback_text_cleaner.extract_pain_text(item.text)

            pipeline_result = self.pipeline.run(
                raw_text=pain_text,
                source=OpportunitySource.REVIEW_SITE,
                industry=item.industry,
            )

            hermes_memory_path = self._write_hermes_memory(pipeline_result)

            manifest = self.manifest_writer.create_manifest(
                status="success",
                query=item.text[:120],
                subreddit=item.source_type,
                industry=item.industry,
                final_workflow_stage="REPORT",
                processed_count=1,
                accepted_count=1,
                rejected_count=0,
                report_paths=[str(pipeline_result.report_path)],
                hermes_memory_count=1,
                hermes_memory_paths=[str(hermes_memory_path)],
            )

            manifest_path = self.manifest_writer.write(manifest)

            registry_path = self.registry_writer.add_run(
                manifest=manifest,
                manifest_path=str(manifest_path),
            )

            return LocalFeedbackResearchItemResult(
                item=item,
                status="success",
                report_path=str(pipeline_result.report_path),
                manifest_path=str(manifest_path),
                registry_path=str(registry_path),
                hermes_memory_path=str(hermes_memory_path),
            )

        except ValueError as exc:
            return LocalFeedbackResearchItemResult(
                item=item,
                status="blocked",
                error=str(exc),
            )

    def _write_hermes_memory(
        self,
        pipeline_result: PipelineResult,
    ) -> Path:
        record = self.memory_hook.build_record(
            source=pipeline_result.opportunity.source.value,
            industry=pipeline_result.opportunity.industry,
            pain_point=pipeline_result.opportunity.pain_point,
            recommendation=pipeline_result.score.recommendation,
            score=pipeline_result.score.total_score,
            report_path=str(pipeline_result.report_path),
        )

        return self.memory_hook.write_record(record)
