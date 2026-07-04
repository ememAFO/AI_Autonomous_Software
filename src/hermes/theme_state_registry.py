import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4


class ThemeStateRegistryError(Exception):
    pass


class InvalidTransitionError(ThemeStateRegistryError):
    pass


class ThemeNotFoundError(ThemeStateRegistryError):
    pass


class DuplicateStateEventError(ThemeStateRegistryError):
    pass


class RegistryIntegrityError(ThemeStateRegistryError):
    pass

@dataclass(frozen=True)
class ThemeStateEvent:
    event_id: str
    theme_id: str
    theme_name: str
    previous_state: str | None
    new_state: str
    trigger: str
    reason: str
    changed_by: str
    related_artifact_id: str
    policy_version: str
    run_id: str
    timestamp: str
    record_hash: str

class ThemeStateRegistry:
    """
    Append-only registry for opportunity/theme lifecycle state.

    Purpose:
    - one active state per theme
    - no hidden state changes
    - no invalid transitions
    - no mutation of old state events

    This registry does not approve building.
    It only records controlled state movement.
    """

    DEFAULT_REGISTRY_PATH = Path("reports/intelligence/theme_state_registry.json")

    ALLOWED_STATES = {
        "RESEARCHED",
        "WATCHING",
        "VALIDATION_READY",
        "VALIDATING",
        "READY_FOR_REVIEW",
        "MVP_PLANNING",
        "REJECTED",
        "ARCHIVED",
    }

    ALLOWED_TRANSITIONS = {
        "RESEARCHED": {"WATCHING", "VALIDATION_READY"},
        "WATCHING": {"VALIDATION_READY", "ARCHIVED"},
        "VALIDATION_READY": {"VALIDATING"},
        "VALIDATING": {"READY_FOR_REVIEW", "REJECTED"},
        "REJECTED": {"ARCHIVED"},
        "READY_FOR_REVIEW": set(),
        "MVP_PLANNING": set(),
        "ARCHIVED": set(),
    }

    INITIAL_STATE = "RESEARCHED"

    HUMAN_REVIEW_RETURN_TRIGGER = "human_review_returned_to_validation"
    HUMAN_REVIEW_APPROVE_TRIGGER = "human_review_approved_mvp_planning"
    HUMAN_REVIEW_REJECT_TRIGGER = "human_review_rejected"
    HUMAN_REVIEW_DECISION_ACTOR = "HumanReviewDecisionService"
    HUMAN_REVIEW_RETURN_ACTOR = HUMAN_REVIEW_DECISION_ACTOR

    TERMINAL_STATES = {
        "READY_FOR_REVIEW",
        "MVP_PLANNING",
        "ARCHIVED",
    }

    def __init__(self, registry_path: str | Path = DEFAULT_REGISTRY_PATH):
        self.registry_path = self._validate_registry_path(Path(registry_path))
        self.registry_path.parent.mkdir(parents=True, exist_ok=True)

    def register_theme(
        self,
        *,
        theme_id: str,
        theme_name: str,
        trigger: str,
        reason: str,
        changed_by: str,
        related_artifact_id: str,
        policy_version: str,
        run_id: str,
    ) -> ThemeStateEvent:
        if self.get_current_state(theme_id) is not None:
            raise DuplicateStateEventError(
                f"Theme already exists in state registry: {theme_id}"
            )

        event = self._build_event(
            theme_id=theme_id,
            theme_name=theme_name,
            previous_state=None,
            new_state=self.INITIAL_STATE,
            trigger=trigger,
            reason=reason,
            changed_by=changed_by,
            related_artifact_id=related_artifact_id,
            policy_version=policy_version,
            run_id=run_id,
        )

        self._append_event(event)
        return event

    def transition(
        self,
        *,
        theme_id: str,
        theme_name: str,
        new_state: str,
        trigger: str,
        reason: str,
        changed_by: str,
        related_artifact_id: str,
        policy_version: str,
        run_id: str,
    ) -> ThemeStateEvent:
        new_state = self._validate_state(new_state)
        current_state = self.get_current_state(theme_id)

        if current_state is None:
            raise ThemeNotFoundError(
                f"Theme must be registered before transition: {theme_id}"
            )

        if current_state == new_state:
            raise DuplicateStateEventError(
                f"Duplicate state change: {theme_id} is already {new_state}"
            )

        self._validate_theme_name(theme_id=theme_id, theme_name=theme_name)
        self._validate_transition(
            previous_state=current_state,
            new_state=new_state,
        )

        event = self._build_event(
            theme_id=theme_id,
            theme_name=theme_name,
            previous_state=current_state,
            new_state=new_state,
            trigger=trigger,
            reason=reason,
            changed_by=changed_by,
            related_artifact_id=related_artifact_id,
            policy_version=policy_version,
            run_id=run_id,
        )

        self._append_event(event)
        return event
    def return_to_validation_after_human_review(
        self,
        *,
        theme_id: str,
        theme_name: str,
        reason: str,
        related_artifact_id: str,
        policy_version: str,
        run_id: str,
    ) -> ThemeStateEvent:
        """
        Records the single controlled reopening path:

        READY_FOR_REVIEW -> VALIDATING

        Generic transitions remain blocked from READY_FOR_REVIEW.
        """
        current_state = self.get_current_state(theme_id)

        if current_state is None:
            raise ThemeNotFoundError(
                f"Theme must be registered before human review return: {theme_id}"
            )

        if current_state != "READY_FOR_REVIEW":
            raise InvalidTransitionError(
                "Human review return requires current state READY_FOR_REVIEW, "
                f"got {current_state}"
            )

        self._validate_theme_name(
            theme_id=theme_id,
            theme_name=theme_name,
        )

        event = self._build_event(
            theme_id=theme_id,
            theme_name=theme_name,
            previous_state=current_state,
            new_state="VALIDATING",
            trigger=self.HUMAN_REVIEW_RETURN_TRIGGER,
            reason=reason,
            changed_by=self.HUMAN_REVIEW_RETURN_ACTOR,
            related_artifact_id=related_artifact_id,
            policy_version=policy_version,
            run_id=run_id,
        )

        self._append_event(event)
        return event

    def approve_mvp_planning_after_human_review(
        self,
        *,
        theme_id: str,
        theme_name: str,
        reason: str,
        related_artifact_id: str,
        policy_version: str,
        run_id: str,
    ) -> ThemeStateEvent:
        """
        Records the controlled human-review outcome:

        READY_FOR_REVIEW -> MVP_PLANNING

        MVP_PLANNING is planning only. It does not approve implementation,
        integration, deployment, or autonomous execution.
        """
        return self._record_human_review_resolution(
            theme_id=theme_id,
            theme_name=theme_name,
            new_state="MVP_PLANNING",
            trigger=self.HUMAN_REVIEW_APPROVE_TRIGGER,
            reason=reason,
            related_artifact_id=related_artifact_id,
            policy_version=policy_version,
            run_id=run_id,
        )

    def reject_after_human_review(
        self,
        *,
        theme_id: str,
        theme_name: str,
        reason: str,
        related_artifact_id: str,
        policy_version: str,
        run_id: str,
    ) -> ThemeStateEvent:
        """Records the controlled human-review outcome READY_FOR_REVIEW -> REJECTED."""
        return self._record_human_review_resolution(
            theme_id=theme_id,
            theme_name=theme_name,
            new_state="REJECTED",
            trigger=self.HUMAN_REVIEW_REJECT_TRIGGER,
            reason=reason,
            related_artifact_id=related_artifact_id,
            policy_version=policy_version,
            run_id=run_id,
        )

    def _record_human_review_resolution(
        self,
        *,
        theme_id: str,
        theme_name: str,
        new_state: str,
        trigger: str,
        reason: str,
        related_artifact_id: str,
        policy_version: str,
        run_id: str,
    ) -> ThemeStateEvent:
        current_state = self.get_current_state(theme_id)

        if current_state is None:
            raise ThemeNotFoundError(
                f"Theme must be registered before human review resolution: {theme_id}"
            )

        if current_state != "READY_FOR_REVIEW":
            raise InvalidTransitionError(
                "Human review resolution requires current state READY_FOR_REVIEW, "
                f"got {current_state}"
            )

        self._validate_theme_name(
            theme_id=theme_id,
            theme_name=theme_name,
        )

        event = self._build_event(
            theme_id=theme_id,
            theme_name=theme_name,
            previous_state=current_state,
            new_state=new_state,
            trigger=trigger,
            reason=reason,
            changed_by=self.HUMAN_REVIEW_DECISION_ACTOR,
            related_artifact_id=related_artifact_id,
            policy_version=policy_version,
            run_id=run_id,
        )

        self._append_event(event)
        return event

    def get_current_state(self, theme_id: str) -> str | None:
        events = self.list_events_for_theme(theme_id)

        if not events:
            return None

        return events[-1].new_state

    def list_events(self) -> list[ThemeStateEvent]:
        data = self._load_registry()

        return [
            ThemeStateEvent(
                event_id=str(item["event_id"]),
                theme_id=str(item["theme_id"]),
                theme_name=str(item["theme_name"]),
                previous_state=item["previous_state"],
                new_state=str(item["new_state"]),
                trigger=str(item["trigger"]),
                reason=str(item["reason"]),
                changed_by=str(item["changed_by"]),
                related_artifact_id=str(item["related_artifact_id"]),
                policy_version=str(item["policy_version"]),
                run_id=str(item["run_id"]),
                timestamp=str(item["timestamp"]),
                record_hash=str(item.get("record_hash", "")),
            )
            for item in data["events"]
        ]

    def list_events_for_theme(self, theme_id: str) -> list[ThemeStateEvent]:
        expected_theme_id = self._validate_required_text("theme_id", theme_id)

        return [
            event for event in self.list_events()
            if event.theme_id == expected_theme_id
        ]

    def _append_event(self, event: ThemeStateEvent) -> None:
        data = self._load_registry()
        data["events"].append(asdict(event))
        self._write_registry(data)

    def _build_event(
        self,
        *,
        theme_id: str,
        theme_name: str,
        previous_state: str | None,
        new_state: str,
        trigger: str,
        reason: str,
        changed_by: str,
        related_artifact_id: str,
        policy_version: str,
        run_id: str,
    ) -> ThemeStateEvent:
        theme_id = self._validate_required_text("theme_id", theme_id)
        theme_name = self._validate_required_text("theme_name", theme_name)
        new_state = self._validate_state(new_state)

        if previous_state is not None:
            previous_state = self._validate_state(previous_state)

        event_without_hash = {
            "event_id": f"state_event_{uuid4().hex}",
            "theme_id": theme_id,
            "theme_name": theme_name,
            "previous_state": previous_state,
            "new_state": new_state,
            "trigger": self._validate_required_text("trigger", trigger),
            "reason": self._validate_required_text("reason", reason),
            "changed_by": self._validate_required_text("changed_by", changed_by),
            "related_artifact_id": self._validate_required_text(
                "related_artifact_id",
                related_artifact_id,
            ),
            "policy_version": self._validate_required_text(
                "policy_version",
                policy_version,
            ),
            "run_id": self._validate_required_text("run_id", run_id),
            "timestamp": datetime.now(UTC).isoformat(),
        }

        return ThemeStateEvent(
            **event_without_hash,
            record_hash=self._generate_record_hash(event_without_hash),
        )

    def _validate_theme_name(self, *, theme_id: str, theme_name: str) -> None:
        events = self.list_events_for_theme(theme_id)

        if not events:
            return

        existing_name = events[-1].theme_name

        if existing_name != theme_name:
            raise ThemeStateRegistryError(
                f"Theme name mismatch for {theme_id}: "
                f"expected {existing_name}, got {theme_name}"
            )

    def _validate_transition(self, *, previous_state: str, new_state: str) -> None:
        if previous_state in self.TERMINAL_STATES:
            raise InvalidTransitionError(
                f"Cannot change terminal state: {previous_state}"
            )

        allowed_next_states = self.ALLOWED_TRANSITIONS.get(previous_state, set())

        if new_state not in allowed_next_states:
            raise InvalidTransitionError(
                f"Invalid state transition: {previous_state} -> {new_state}"
            )

    def _validate_state(self, state: str) -> str:
        state = self._validate_required_text("state", state).upper()

        if state not in self.ALLOWED_STATES:
            raise ThemeStateRegistryError(f"Invalid theme state: {state}")

        return state

    def _validate_required_text(self, field_name: str, value: str) -> str:
        if not isinstance(value, str):
            raise ThemeStateRegistryError(f"{field_name} must be a string")

        cleaned = value.strip()

        if not cleaned:
            raise ThemeStateRegistryError(f"{field_name} is required")

        return cleaned

    def _load_registry(self) -> dict:
        if not self.registry_path.exists():
            return {"events": []}

        try:
            data = json.loads(self.registry_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ThemeStateRegistryError(
                "Theme state registry contains invalid JSON"
            ) from exc

        if not isinstance(data, dict):
            raise ThemeStateRegistryError(
                "Theme state registry must contain a JSON object"
            )

        if "events" not in data:
            data["events"] = []

        if not isinstance(data["events"], list):
            raise ThemeStateRegistryError(
                "Theme state registry 'events' field must be a list"
            )

        return data

    def _write_registry(self, data: dict) -> None:
        self.registry_path.write_text(
            json.dumps(data, indent=2, sort_keys=True),
            encoding="utf-8",
        )

    def verify_integrity(self) -> None:
        for event in self.list_events():
            event_dict = asdict(event)
            stored_hash = event_dict.pop("record_hash", "")

            if not stored_hash:
                raise RegistryIntegrityError(
                    f"Missing record hash for event: {event.event_id}"
                )

            expected_hash = self._generate_record_hash(event_dict)

            if stored_hash != expected_hash:
                raise RegistryIntegrityError(
                    f"Record hash mismatch for event: {event.event_id}"
                )

    def _generate_record_hash(self, event_dict: dict) -> str:
        normalized = json.dumps(
            event_dict,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")

        return hashlib.sha256(normalized).hexdigest()

    @staticmethod
    def _is_within(path: Path, root: Path) -> bool:
        try:
            path.relative_to(root)
            return True
        except ValueError:
            return False

    def _validate_registry_path(self, registry_path: Path) -> Path:
        resolved = registry_path.resolve()
        project_root = Path.cwd().resolve()
        allowed_root = (project_root / "reports" / "intelligence").resolve()

        if not self._is_within(resolved, allowed_root):
            raise ThemeStateRegistryError(
                "Theme state registry must stay inside reports/intelligence"
            )

        if resolved.suffix != ".json":
            raise ThemeStateRegistryError(
                "Theme state registry must be a JSON file"
            )

        return resolved
