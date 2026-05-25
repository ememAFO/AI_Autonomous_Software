import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.research.research_planner import ResearchPlanner, ResearchPlannerError
from src.utils.audit_logger import AuditEvent, AuditLogger


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create a controlled research plan for an industry."
    )

    parser.add_argument(
        "--industry",
        required=True,
        help="Industry to plan research for. Example: sales, saas, healthcare, accounting",
    )

    return parser.parse_args()


def main() -> int:
    args = parse_args()

    try:
        planner = ResearchPlanner()
        plan = planner.plan_from_text(args.industry)

        source_names = [source.name for source in plan.recommended_sources]
        blocked_source_names = [source.name for source in plan.blocked_sources]

        AuditLogger().log(
            AuditEvent(
                action="research_plan",
                status="success",
                details={
                    "industry": plan.industry.value,
                    "recommended_sources": source_names,
                    "blocked_sources": blocked_source_names,
                    "suggested_queries": plan.suggested_queries,
                },
            )
        )

        print("\nResearch Plan")
        print("-------------")
        print(f"Industry: {plan.industry.value}")
        print(f"Description: {plan.industry_profile.description}")

        print("\nPain Themes:")
        for theme in plan.industry_profile.pain_themes:
            print(f"- {theme}")

        print("\nRecommended Sources:")
        for source in plan.recommended_sources:
            api_note = "requires API" if source.requires_api else "no API required"
            print(f"- {source.name} ({source.source_type.value}, {api_note})")

        print("\nSuggested Queries:")
        for query in plan.suggested_queries:
            print(f"- {query}")

        print("\nBlocked Sources:")
        if plan.blocked_sources:
            for source in plan.blocked_sources:
                print(f"- {source.name}: {source.blocked_reason}")
        else:
            print("- None")

        return 0

    except ResearchPlannerError as exc:
        AuditLogger().log(
            AuditEvent(
                action="research_plan",
                status="blocked",
                details={
                    "industry": args.industry,
                    "error": str(exc),
                },
            )
        )

        print(f"Research plan blocked: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
