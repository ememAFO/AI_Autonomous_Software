from dataclasses import dataclass
from pathlib import Path

from src.hermes.research_memory import (
    HermesResearchMemoryHook,
    HermesResearchMemoryRecord,
)
from src.research.reddit_research_job import RedditResearchJobResult


@dataclass(frozen=True)
class HermesMemorySyncResult:
    written_count: int
    memory_paths: list[Path]


class HermesResearchMemorySync:
    """
    Converts accepted research pipeline results into Hermes memory records.

    Security rules:
    - Only accepted pipeline results are converted.
    - Only structured opportunity data is stored.
    - No credentials, secrets, shell commands, or deployment instructions are stored.
    - Memory writes go through HermesResearchMemoryHook path validation.
    """

    def __init__(self, memory_hook: HermesResearchMemoryHook | None = None):
        self.memory_hook = memory_hook or HermesResearchMemoryHook()

    def sync_from_reddit_job(
        self,
        job_result: RedditResearchJobResult,
    ) -> HermesMemorySyncResult:
        memory_paths: list[Path] = []

        for pipeline_result in job_result.adapter_result.results:
            opportunity = pipeline_result.opportunity
            score = pipeline_result.score

            record: HermesResearchMemoryRecord = self.memory_hook.build_record(
                source=opportunity.source.value,
                industry=opportunity.industry,
                pain_point=opportunity.pain_point,
                recommendation=score.recommendation,
                score=score.total_score,
                report_path=str(pipeline_result.report_path),
            )

            memory_path = self.memory_hook.write_record(record)
            memory_paths.append(memory_path)

        return HermesMemorySyncResult(
            written_count=len(memory_paths),
            memory_paths=memory_paths,
        )
