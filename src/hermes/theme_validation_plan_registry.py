import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

from src.hermes.theme_validation_plan import ThemeValidationPlan
from src.utils.path_normalizer import PathNormalizerError, ProjectPathNormalizer


class ThemeValidationPlanRegistryError(Exception):
    pass


@dataclass(frozen=True)
class ThemeValidationPlanRegistryEntry:
    theme: str
    readiness: str
    readiness_score: float
    output_path: str
    timestamp: str
    status: str = "planned"


class ThemeValidationPlanRegistry:
    """
    Maintains an index of generated validation plans.

    Purpose:
    - keep validation plans traceable
    - avoid losing generated validation artifacts
    - support future workflow stages such as validation_started, validated, rejected, or build_candidate

    Security:
    - writes only inside reports/intelligence
    - stores metadata only
    - does not approve building
    """

    DEFAULT_REGISTRY_PATH = Path("reports/intelligence/validation_plan_index.json")

    def __init__(self, registry_path: str | Path = DEFAULT_REGISTRY_PATH):
        self.registry_path = self._validate_registry_path(Path(registry_path))
        self.path_normalizer = ProjectPathNormalizer()
        self.registry_path.parent.mkdir(parents=True, exist_ok=True)

    def add_plan(
        self,
        plan: ThemeValidationPlan,
        *,
        status: str = "planned",
    ) -> ThemeValidationPlanRegistryEntry:
        entry = ThemeValidationPlanRegistryEntry(
            theme=plan.theme,
            readiness=plan.readiness,
            readiness_score=plan.readiness_score,
            output_path=plan.output_path,
            timestamp=datetime.now(UTC).isoformat(),
            status=status,
        )

        data = self._load_registry()
        data["plans"].append(asdict(entry))
        self._write_registry(data)

        return entry

    def list_entries(self) -> list[ThemeValidationPlanRegistryEntry]:
        data = self._load_registry()

        return [
            ThemeValidationPlanRegistryEntry(
                theme=str(item["theme"]),
                readiness=str(item["readiness"]),
                readiness_score=float(item["readiness_score"]),
                output_path=str(item["output_path"]),
                timestamp=str(item["timestamp"]),
                status=str(item.get("status", "planned")),
            )
            for item in data["plans"]
        ]

    def _load_registry(self) -> dict:
        if not self.registry_path.exists():
            return {"plans": []}

        try:
            data = json.loads(self.registry_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ThemeValidationPlanRegistryError(
                "Validation plan registry contains invalid JSON"
            ) from exc

        if not isinstance(data, dict):
            raise ThemeValidationPlanRegistryError(
                "Validation plan registry must contain a JSON object"
            )

        if "plans" not in data:
            data["plans"] = []

        if not isinstance(data["plans"], list):
            raise ThemeValidationPlanRegistryError(
                "Validation plan registry 'plans' field must be a list"
            )

        return data

    def _write_registry(self, data: dict) -> None:
        self.registry_path.write_text(
            json.dumps(data, indent=2, sort_keys=True),
            encoding="utf-8",
        )

    def _validate_registry_path(self, registry_path: Path) -> Path:
        resolved = registry_path.resolve()
        project_root = Path.cwd().resolve()
        allowed_root = (project_root / "reports" / "intelligence").resolve()

        if not self._is_within(resolved, allowed_root):
            raise ThemeValidationPlanRegistryError(
                "Validation plan registry must stay inside reports/intelligence"
            )

        if resolved.suffix != ".json":
            raise ThemeValidationPlanRegistryError(
                "Validation plan registry must be a JSON file"
            )

        return resolved

    @staticmethod
    def _is_within(path: Path, root: Path) -> bool:
        try:
            path.relative_to(root)
            return True
        except ValueError:
            return False
