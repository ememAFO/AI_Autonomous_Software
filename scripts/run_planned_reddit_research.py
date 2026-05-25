import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.research.planned_reddit_research_runner import PlannedRedditResearchRunner
from src.research.reddit_job_planner import RedditJobPlannerError
from src.utils.audit_logger import AuditEvent, AuditLogger


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run planned Reddit research jobs for an industry."
    )

    parser.add_argument(
        "--industry",
        required=True,
        help="Industry to run planned research for. Example: sales, saas, accounting",
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=2,
        help="Maximum mocked posts per planned job.",
    )

    return parser.parse_args()


def main() -> int:
    args = parse_args()

    try:
        runner = PlannedRedditResearchRunner()

        batch_result = runner.run_for_industry(
            industry_text=args.industry,
            limit_per_job=args.limit,
        )

        AuditLogger().log(
            AuditEvent(
                action="planned_reddit_research_batch",
                status="success",
                details={
                    "industry": batch_result.industry,
                    "planned_count": batch_result.planned_count,
                    "successful_count": batch_result.successful_count,
                    "blocked_count": batch_result.blocked_count,
                    "jobs": [
                        {
                            "status": result.status,
                            "query": result.planned_job.query.query,
                            "subreddit": result.planned_job.query.subreddit,
                            "processed_count": result.processed_count,
                            "accepted_count": result.accepted_count,
                            "rejected_count": result.rejected_count,
                            "final_workflow_stage": result.final_workflow_stage,
                            "manifest_path": result.manifest_path,
                            "registry_path": result.registry_path,
                            "hermes_memory_count": result.hermes_memory_count,
                            "error": result.error,
                        }
                        for result in batch_result.results
                    ],
                },
            )
        )

        print("\nPlanned Reddit Research Batch Complete")
        print("--------------------------------------")
        print(f"Industry: {batch_result.industry}")
        print(f"Planned Jobs: {batch_result.planned_count}")
        print(f"Successful Jobs: {batch_result.successful_count}")
        print(f"Blocked Jobs: {batch_result.blocked_count}")

        print("\nJob Results:")
        for index, result in enumerate(batch_result.results, start=1):
            print(
                f"{index}. {result.status.upper()} | "
                f"subreddit={result.planned_job.query.subreddit} | "
                f"query='{result.planned_job.query.query}' | "
                f"accepted={result.accepted_count} | "
                f"stage={result.final_workflow_stage}"
            )

            if result.error:
                print(f"   Error: {result.error}")

        return 0

    except RedditJobPlannerError as exc:
        AuditLogger().log(
            AuditEvent(
                action="planned_reddit_research_batch",
                status="blocked",
                details={
                    "industry": args.industry,
                    "error": str(exc),
                },
            )
        )

        print(f"Planned Reddit research blocked: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
