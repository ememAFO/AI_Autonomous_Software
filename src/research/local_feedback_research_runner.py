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
from src.research.pain_reasoner import PainReasoner
from src.research.pain_analysis import PainDecision
from src.research.models import Opportunity
from src.research.scoring import OpportunityScoringEngine
from src.research.report_generator import OpportunityReportGenerator


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
        pain_reasoner: PainReasoner | None = None,
        scorer: OpportunityScoringEngine | None = None,
        report_generator: OpportunityReportGenerator | None = None,

    ):
        self.adapter = adapter or LocalCSVFeedbackAdapter()
        self.pipeline = pipeline or ResearchPipeline()
        self.manifest_writer = manifest_writer or ResearchRunManifestWriter()
        self.registry_writer = registry_writer or ResearchRunRegistryWriter()
        self.memory_hook = memory_hook or HermesResearchMemoryHook()
        self.feedback_text_cleaner = feedback_text_cleaner or FeedbackTextCleaner()
        self.pain_reasoner = pain_reasoner or PainReasoner()
        self.scorer = scorer or OpportunityScoringEngine()
        self.report_generator = report_generator or OpportunityReportGenerator()

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

            try:
                pipeline_result = self.pipeline.run(
                    raw_text=pain_text,
                    source=OpportunitySource.REVIEW_SITE,
                    industry=item.industry,
                )
            except ValueError:
                pipeline_result = self._fallback_from_pain_reasoner(
                    pain_text=pain_text,
                    item=item,
                )

            hermes_memory_path = self._write_hermes_memory(pipeline_result)

            manifest = self.manifest_writer.create_manifest(
                status="success",
                query=pain_text[:120],
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

    def _fallback_from_pain_reasoner(
        self,
        *,
        pain_text: str,
        item: LocalFeedbackItem,
    ) -> PipelineResult:
        analysis = self.pain_reasoner.analyze(
            pain_text,
            industry=item.industry,
        )

        if analysis.decision != PainDecision.ACCEPT:
            raise ValueError("No valid business pain detected")

        opportunity = Opportunity(
            title=self._title_from_analysis(analysis.pain_category.value),
            pain_point=analysis.symptom,
            source=OpportunitySource.REVIEW_SITE,
            industry=item.industry,
            frequency=self._score_from_confidence(analysis.confidence),
            urgency=self._urgency_from_analysis(analysis.commercial_signal.value),
            monetization=self._monetization_from_analysis(analysis.commercial_signal.value),
            retention_impact=6.0,
            competition_gap=5.0,
            automation_potential=7.0,
            implementation_difficulty=5.0,
            evidence=analysis.evidence or [analysis.symptom],
            suggested_mvp=self._suggested_mvp_from_analysis(analysis.pain_category.value),
        )

        challenge_result = self.pipeline.challenger.challenge(opportunity)

        if not challenge_result.should_continue:
            raise ValueError(
                f"Opportunity rejected by strategic validation: "
                f"{challenge_result.recommendation}"
            )

        score = self.scorer.score(opportunity)

        report_path = self.report_generator.generate(
            score=score,
            challenge_result=challenge_result,
        )

        return PipelineResult(
            raw_text=pain_text,
            opportunity=opportunity,
            challenge_result=challenge_result,
            score=score,
            report_path=report_path,
        )

    def _title_from_analysis(self, category: str) -> str:
        title_map = {
            "integration": "Integration Workflow Pain",
            "support": "Support Resolution Pain",
            "onboarding": "Onboarding Friction",
            "workflow": "Workflow Automation Opportunity",
            "economic": "Pricing and ROI Pain",
            "ux_friction": "Product Usability Friction",
        }

        return title_map.get(category, "Feedback Pain Opportunity")

    def _suggested_mvp_from_analysis(self, category: str) -> str:
        mvp_map = {
            "integration": "Integration issue tracker and deduplication assistant",
            "support": "Support escalation and resolution assistant",
            "onboarding": "AI onboarding and setup assistant",
            "workflow": "Workflow automation assistant",
            "economic": "Pricing-value analysis and plan guidance assistant",
            "ux_friction": "UX friction detection and guidance assistant",
        }

        return mvp_map.get(category, "Validation-first feedback assistant")

    def _score_from_confidence(self, confidence: float) -> float:
        return round(min(max(confidence * 10, 1.0), 10.0), 1)

    def _urgency_from_analysis(self, commercial_signal: str) -> float:
        if commercial_signal == "strong":
            return 8.0

        if commercial_signal == "moderate":
            return 6.0

        return 4.0

    def _monetization_from_analysis(self, commercial_signal: str) -> float:
        if commercial_signal == "strong":
            return 8.0

        if commercial_signal == "moderate":
            return 6.0

        return 3.0
