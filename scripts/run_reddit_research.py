import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.adapters.reddit_fetcher import RedditFetcherError, RedditResearchQuery
from src.research.research_orchestrator import ResearchOrchestrator
from src.utils.audit_logger import AuditEvent, AuditLogger

ALLOWED_SUBREDDITS = {
    "smallbusiness",
    "entrepreneur",
    "entrepreneurs",
    "saaS",
    "agency",
    "plumbing",
    "roofing",
    "HVAC",
    "dentistry",
    "salon",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run a controlled Reddit-style research job."
    )

    parser.add_argument(
        "--query",
        default="manual follow up",
        help="Research query to search for. Example: 'manual follow up'",
    )

    parser.add_argument(
        "--subreddit",
        default="smallbusiness",
        help="Allowed subreddit to research.",
    )

    parser.add_argument(
        "--industry",
        default="home services",
        help="Industry label for the opportunity report.",
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=2,
        help="Maximum number of posts to process.",
    )

    return parser.parse_args()


def validate_cli_inputs(args: argparse.Namespace) -> None:
    if not args.query.strip():
        raise ValueError("Query cannot be empty")

    if not args.industry.strip():
        raise ValueError("Industry cannot be empty")

    if args.limit < 1 or args.limit > 25:
        raise ValueError("Limit must be between 1 and 25")

    if args.subreddit not in ALLOWED_SUBREDDITS:
        raise ValueError(
            f"Subreddit '{args.subreddit}' is not allowed. "
            f"Allowed values: {', '.join(sorted(ALLOWED_SUBREDDITS))}"
        )


def main() -> int:
    args = parse_args()

    try:
        validate_cli_inputs(args)

        orchestrator = ResearchOrchestrator()
        audit_logger = AuditLogger()

        orchestrator_result = orchestrator.run_reddit_research(
            research_query=RedditResearchQuery(
                query=args.query,
                subreddit=args.subreddit,
                limit=args.limit,
            ),
            industry=args.industry,
        )

        result = orchestrator_result.job_result

        print("\nReddit Research Job Complete")
        print("----------------------------")
        print(f"Query: {result.query.query}")
        print(f"Subreddit: {result.query.subreddit}")
        print(f"Processed: {result.processed_count}")
        print(f"Accepted: {result.accepted_count}")
        print(f"Rejected: {result.rejected_count}")
        print(f"Final Workflow Stage: {orchestrator_result.final_stage}")

        if result.adapter_result.results:
            print("\nGenerated Reports:")
            for pipeline_result in result.adapter_result.results:
                print(f"- {pipeline_result.report_path}")

        audit_logger.log(
            AuditEvent(
                action="reddit_research_job",
                status="success",
                details={
                    "query": result.query.query,
                    "subreddit": result.query.subreddit,
                    "industry": args.industry,
                    "processed_count": result.processed_count,
                    "accepted_count": result.accepted_count,
                    "rejected_count": result.rejected_count,
                    "final_workflow_stage": orchestrator_result.final_stage.value,
                    "report_paths": [
                        str(pipeline_result.report_path)
                        for pipeline_result in result.adapter_result.results
                    ],
                },
            )
        )

        return 0

    except (ValueError, RedditFetcherError) as exc:
        AuditLogger().log(
            AuditEvent(
                action="reddit_research_job",
                status="blocked",
                details={
                    "error": str(exc),
                },
            )
        )

        print(f"Research job blocked: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
