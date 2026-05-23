from dataclasses import dataclass
from pathlib import Path

from src.analyzers.pain_extractor import PainExtractor
from src.research.models import Opportunity, OpportunitySource
from src.research.opportunity_builder import OpportunityBuilder
from src.research.report_generator import OpportunityReportGenerator
from src.research.scoring import (
    OpportunityScore,
    OpportunityScoringEngine,
)


@dataclass(frozen=True)
class PipelineResult:
    raw_text: str
    opportunity: Opportunity
    score: OpportunityScore
    report_path: Path


class ResearchPipeline:
    """
    Controlled research pipeline.

    Pipeline stages:
    1. Extract pain
    2. Build opportunity
    3. Score opportunity
    4. Generate report

    Fails closed:
    - invalid pain signals stop the workflow
    - invalid opportunities stop the workflow
    """

    def __init__(self):
        self.extractor = PainExtractor()
        self.builder = OpportunityBuilder()
        self.scorer = OpportunityScoringEngine()
        self.report_generator = OpportunityReportGenerator()

    def run(
        self,
        raw_text: str,
        source: OpportunitySource,
        industry: str,
    ) -> PipelineResult:
        signal = self.extractor.extract(raw_text)

        if not signal.is_business_pain:
            raise ValueError("No valid business pain detected")

        opportunity = self.builder.build_from_pain_signal(
            signal=signal,
            source=source,
            industry=industry,
        )

        score = self.scorer.score(opportunity)

        report_path = self.report_generator.generate(score)

        return PipelineResult(
            raw_text=raw_text,
            opportunity=opportunity,
            score=score,
            report_path=report_path,
        )
