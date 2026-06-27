import argparse
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


from src.hermes.public_research_synthesis import (
    PublicResearchSynthesisError,
    PublicResearchSynthesisGenerator,
)
from src.hermes.validation_evidence_log import (
    ValidationEvidenceLog,
    ValidationEvidenceLogError,
)
from src.utils.audit_logger import AuditEvent, AuditLogger


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Generate a read-only synthesis of gate-safe public validation "
            "research."
        )
    )

    parser.add_argument("--theme", required=True)

    parser.add_argument(
        "--evidence-log-path",
        default="reports/intelligence/validation_evidence_log.json",
    )

    parser.add_argument(
        "--output-path",
        default=None,
        help=(
            "Optional Markdown output path inside "
            "reports/intelligence/public_research_synthesis."
        ),
    )

    return parser.parse_args()


def _display_path(path: Path) -> str:
    project_root = Path.cwd().resolve()

    try:
        return str(path.resolve().relative_to(project_root))
    except ValueError:
        return str(path)


def main() -> int:
    args = parse_args()

    try:
        evidence_log = ValidationEvidenceLog(log_path=args.evidence_log_path)
        generator = PublicResearchSynthesisGenerator(
            evidence_log=evidence_log,
        )

        synthesis, written_path = generator.generate(
            theme=args.theme,
            output_path=args.output_path,
        )
    except (
        PublicResearchSynthesisError,
        ValidationEvidenceLogError,
    ) as exc:
        AuditLogger().log(
            AuditEvent(
                action="public_research_synthesis",
                status="blocked",
                details={"error": str(exc)},
            )
        )
        print(f"Public research synthesis blocked: {exc}", file=sys.stderr)
        return 1

    AuditLogger().log(
        AuditEvent(
            action="public_research_synthesis",
            status="success",
            details={
                "theme": synthesis.theme,
                "evidence_status": synthesis.evidence_status,
                "gate_safe_public_entries": synthesis.gate_safe_public_entries,
                "public_dataset_entries": synthesis.public_dataset_entries,
                "public_competitor_entries": synthesis.public_competitor_entries,
                "output_path": _display_path(written_path),
            },
        )
    )

    print("\nPublic Research Synthesis Generated")
    print("-----------------------------------")
    print(f"Theme: {synthesis.theme}")
    print(f"Validation Evidence Status: {synthesis.evidence_status}")
    print(
        "Gate-Safe Public Research Entries: "
        f"{synthesis.gate_safe_public_entries}"
    )
    print(f"Public Dataset Entries: {synthesis.public_dataset_entries}")
    print(
        "Public Competitor Entries: "
        f"{synthesis.public_competitor_entries}"
    )
    print(
        "Public Supporting Entries: "
        f"{synthesis.public_supporting_entries}"
    )
    print(
        "Public Challenging Entries: "
        f"{synthesis.public_opposing_entries}"
    )
    print(
        "Entries Outside Public Synthesis: "
        f"{synthesis.entries_outside_public_synthesis}"
    )
    print("Decision Boundary: Public research synthesis complete; first-party pilot required.")
    print(f"Output Path: {_display_path(written_path)}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
