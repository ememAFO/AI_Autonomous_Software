import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.research.reddit_job_planner import RedditJobPlanner, RedditJobPlannerError
from src.utils.audit_logger import AuditEvent, AuditLogger


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Plan safe Reddit research jobs for an industry."
    )

    parser.add_argument(
        "--industry",
        required=True,
        help="Industry to plan jobs for. Example: sales, saas, accounting",
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=5,
        help="Maximum mocked posts per planned job.",
    )

    return parser.parse_args()


def main() -> int:
    args = parse_args()

    try:
        planner = RedditJobPlanner()
        plan = planner.plan_from_text(
            industry_text=args.industry,
            limit_per_job=args.limit,
        )

        planned_jobs = [
            {
                "industry": job.industry.value,
                "query": job.query.query,
                "subreddit": job.query.subreddit,
                "limit": job.query.limit,
            }
            for job in plan.jobs
        ]

        AuditLogger().log(
            AuditEvent(
                action="reddit_job_plan",
                status="success",
                details={
                    "industry": plan.industry.value,
                    "planned_jobs": planned_jobs,
                    "job_count": len(planned_jobs),
                    "skipped_reasons": plan.skipped_reasons,
                },
            )
        )

        print("\nReddit Job Plan")
        print("---------------")
        print(f"Industry: {plan.industry.value}")
        print(f"Planned Jobs: {len(plan.jobs)}")

        print("\nJobs:")
        for index, job in enumerate(plan.jobs, start=1):
            print(
                f"{index}. subreddit={job.query.subreddit} | "
                f"query='{job.query.query}' | "
                f"limit={job.query.limit}"
            )

        print("\nSkipped Reasons:")
        if plan.skipped_reasons:
            for reason in plan.skipped_reasons:
                print(f"- {reason}")
        else:
            print("- None")

        return 0

    except RedditJobPlannerError as exc:
        AuditLogger().log(
            AuditEvent(
                action="reddit_job_plan",
                status="blocked",
                details={
                    "industry": args.industry,
                    "error": str(exc),
                },
            )
        )

        print(f"Reddit job plan blocked: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
