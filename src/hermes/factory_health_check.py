from dataclasses import dataclass
from pathlib import Path

from src.hermes.validation_evidence_summary import ValidationEvidenceSummarizer

from src.hermes.theme_state_registry import (
    RegistryIntegrityError,
    ThemeStateRegistry,
    ThemeStateRegistryError,
)
from src.hermes.theme_validation_plan_registry import (
    ThemeValidationPlanRegistry,
    ThemeValidationPlanRegistryError,
)
from src.hermes.validation_evidence_log import (
    ValidationEvidenceLog,
    ValidationEvidenceLogError,
)


class FactoryHealthCheckError(Exception):
    pass


@dataclass(frozen=True)
class FactoryHealthCheckResult:
    check_name: str
    status: str
    message: str


@dataclass(frozen=True)
class FactoryHealthReport:
    status: str
    results: list[FactoryHealthCheckResult]

    @property
    def passed(self) -> bool:
        return self.status == "PASS"


class FactoryHealthChecker:
    """
    Basic structural health check for the AI autonomous software factory.

    Purpose:
    - verify registries are readable
    - verify theme state integrity
    - detect invalid or orphaned validation artifacts
    - provide a simple pass/fail structural report

    This does not approve building.
    """

    def __init__(
        self,
        *,
        state_registry: ThemeStateRegistry | None = None,
        validation_plan_registry: ThemeValidationPlanRegistry | None = None,
        validation_evidence_log: ValidationEvidenceLog | None = None,
    ):
        self.state_registry = state_registry or ThemeStateRegistry()
        self.validation_plan_registry = (
            validation_plan_registry or ThemeValidationPlanRegistry()
        )
        self.validation_evidence_log = validation_evidence_log or ValidationEvidenceLog()

        self.validation_evidence_summarizer = ValidationEvidenceSummarizer(
            self.validation_evidence_log
        )

    def run(self) -> FactoryHealthReport:
        results = [
            self._check_theme_state_registry_readable(),
            self._check_theme_state_registry_integrity(),
            self._check_validation_plan_registry_readable(),
            self._check_validation_evidence_log_readable(),
            self._check_validation_evidence_plan_links(),
            self._check_validation_evidence_readiness(),
        ]

        status = "PASS" if all(result.status == "PASS" for result in results) else "FAIL"

        return FactoryHealthReport(status=status, results=results)

    def _check_theme_state_registry_readable(self) -> FactoryHealthCheckResult:
        try:
            events = self.state_registry.list_events()
        except ThemeStateRegistryError as exc:
            return FactoryHealthCheckResult(
                check_name="theme_state_registry_readable",
                status="FAIL",
                message=f"Theme state registry is not readable: {exc}",
            )

        return FactoryHealthCheckResult(
            check_name="theme_state_registry_readable",
            status="PASS",
            message=f"Theme state registry readable. Events: {len(events)}",
        )

    def _check_theme_state_registry_integrity(self) -> FactoryHealthCheckResult:
        try:
            self.state_registry.verify_integrity()
        except RegistryIntegrityError as exc:
            return FactoryHealthCheckResult(
                check_name="theme_state_registry_integrity",
                status="FAIL",
                message=f"Theme state registry integrity failed: {exc}",
            )
        except ThemeStateRegistryError as exc:
            return FactoryHealthCheckResult(
                check_name="theme_state_registry_integrity",
                status="FAIL",
                message=f"Theme state registry check failed: {exc}",
            )

        return FactoryHealthCheckResult(
            check_name="theme_state_registry_integrity",
            status="PASS",
            message="Theme state registry hashes are valid.",
        )

    def _check_validation_plan_registry_readable(self) -> FactoryHealthCheckResult:
        try:
            plans = self.validation_plan_registry.list_entries()
        except ThemeValidationPlanRegistryError as exc:
            return FactoryHealthCheckResult(
                check_name="validation_plan_registry_readable",
                status="FAIL",
                message=f"Validation plan registry is not readable: {exc}",
            )

        return FactoryHealthCheckResult(
            check_name="validation_plan_registry_readable",
            status="PASS",
            message=f"Validation plan registry readable. Plans: {len(plans)}",
        )

    def _check_validation_evidence_log_readable(self) -> FactoryHealthCheckResult:
        try:
            entries = self.validation_evidence_log.list_entries()
        except ValidationEvidenceLogError as exc:
            return FactoryHealthCheckResult(
                check_name="validation_evidence_log_readable",
                status="FAIL",
                message=f"Validation evidence log is not readable: {exc}",
            )

        return FactoryHealthCheckResult(
            check_name="validation_evidence_log_readable",
            status="PASS",
            message=f"Validation evidence log readable. Entries: {len(entries)}",
        )

    def _check_validation_evidence_plan_links(self) -> FactoryHealthCheckResult:
        try:
            evidence_entries = self.validation_evidence_log.list_entries()
        except ValidationEvidenceLogError as exc:
            return FactoryHealthCheckResult(
                check_name="validation_evidence_plan_links",
                status="FAIL",
                message=f"Could not read validation evidence log: {exc}",
            )

        missing_paths = []

        for entry in evidence_entries:
            plan_path = Path(entry.validation_plan_path)

            if not plan_path.exists():
                missing_paths.append(entry.validation_plan_path)

        if missing_paths:
            unique_missing = sorted(set(missing_paths))
            return FactoryHealthCheckResult(
                check_name="validation_evidence_plan_links",
                status="FAIL",
                message=(
                    "Validation evidence references missing validation plans: "
                    + ", ".join(unique_missing)
                ),
            )

        return FactoryHealthCheckResult(
            check_name="validation_evidence_plan_links",
            status="PASS",
            message="All validation evidence entries reference existing plan paths.",
        )


    def _check_validation_evidence_readiness(self) -> FactoryHealthCheckResult:
        try:
            evidence_entries = self.validation_evidence_log.list_entries()
            validation_plans = self.validation_plan_registry.list_entries()
        except ValidationEvidenceLogError as exc:
            return FactoryHealthCheckResult(
                check_name="validation_evidence_readiness",
                status="FAIL",
                message=f"Could not read validation evidence log: {exc}",
            )
        except ThemeValidationPlanRegistryError as exc:
            return FactoryHealthCheckResult(
                check_name="validation_evidence_readiness",
                status="FAIL",
                message=f"Could not read validation plan registry: {exc}",
            )

        themes = sorted(
            {
                entry.theme
                for entry in evidence_entries
                if entry.theme.strip()
            }
            | {
                plan.theme
                for plan in validation_plans
                if plan.theme.strip()
            }
        )

        if not themes:
            return FactoryHealthCheckResult(
                check_name="validation_evidence_readiness",
                status="PASS",
                message="No validation themes found yet.",
            )

        summaries = [
            self.validation_evidence_summarizer.summarize_theme(theme)
            for theme in themes
        ]

        summary_messages = [
            (
                f"{summary.theme}: {summary.status} "
                f"(total={summary.total_entries}, "
                f"primary={summary.primary_entries}, "
                f"secondary={summary.secondary_entries}, "
                f"risk={summary.risk_entries}). "
                f"Next action: {summary.recommended_next_action}"
            )
            for summary in summaries
        ]

        return FactoryHealthCheckResult(
            check_name="validation_evidence_readiness",
            status="PASS",
            message=(
                "Validation evidence readiness checked. "
                + " | ".join(summary_messages)
            ),
        )
