import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.hermes.research_memory_sync import HermesResearchMemorySync
from src.research.run_manifest import ResearchRunManifestWriter
from src.adapters.reddit_fetcher import RedditFetcherError, RedditResearchQuery
from src.research.research_orchestrator import ResearchOrchestrator
from src.utils.audit_logger import AuditEvent, AuditLogger
from src.research.run_registry import ResearchRunRegistryWriter

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
        manifest_writer = ResearchRunManifestWriter()
        registry_writer = ResearchRunRegistryWriter()
        memory_sync = HermesResearchMemorySync()

        orchestrator_result = orchestrator.run_reddit_research(
            research_query=RedditResearchQuery(
                query=args.query,
                subreddit=args.subreddit,
                limit=args.limit,
            ),
            industry=args.industry,
        )

        result = orchestrator_result.job_result

        report_paths = [
            str(pipeline_result.report_path)
            for pipeline_result in result.adapter_result.results
        ]

        memory_sync_result = memory_sync.sync_from_reddit_job(result)

        memory_paths = [
            str(memory_path)
            for memory_path in memory_sync_result.memory_paths
        ]

        manifest = manifest_writer.create_manifest(
            status="success",
            query=result.query.query,
            subreddit=result.query.subreddit,
            industry=args.industry,
            final_workflow_stage=orchestrator_result.final_stage.value,
            processed_count=result.processed_count,
            accepted_count=result.accepted_count,
            rejected_count=result.rejected_count,
            report_paths=report_paths,
            hermes_memory_count=memory_sync_result.written_count,
            hermes_memory_paths=memory_paths,
        )

        manifest_path = manifest_writer.write(manifest)

        registry_path = registry_writer.add_run(
            manifest=manifest,
            manifest_path=str(manifest_path),
        )

        memory_sync_result = memory_sync.sync_from_reddit_job(result)

        memory_paths = [
            str(memory_path)
            for memory_path in memory_sync_result.memory_paths
        ]


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
                    "manifest_path": str(manifest_path),
                    "report_paths": report_paths,
                    "registry_path": str(registry_path),
                    "hermes_memory_count": memory_sync_result.written_count,
                    "hermes_memory_paths": memory_paths,
                },
            )
        )

        print("\nReddit Research Job Complete")
        print("----------------------------")
        print(f"Query: {result.query.query}")
        print(f"Subreddit: {result.query.subreddit}")
        print(f"Processed: {result.processed_count}")
        print(f"Accepted: {result.accepted_count}")
        print(f"Rejected: {result.rejected_count}")
        print(f"Final Workflow Stage: {orchestrator_result.final_stage}")
        print("\nResearch Run Registry:")
        print(f"- {registry_path}")
        print("\nHermes Memory Records:")

        if memory_paths:
            for memory_path in memory_paths:
                print(f"- {memory_path}")
        else:
            print("- No Hermes memory records written.")

        if report_paths:
            print("\nGenerated Reports:")
            for report_path in report_paths:
                print(f"- {report_path}")

        print("\nRun Manifest:")
        print(f"- {manifest_path}")

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
