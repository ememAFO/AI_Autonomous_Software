"""Capture governed Stage 4G v0.2 operational measurements."""

from __future__ import annotations

import hashlib
import json
import math
import re
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from src.research.operational_measurement_storage import (
    ControlledMeasurementStore,
    OperationalMeasurementCandidateStore,
    OperationalMeasurementCaptureRegistry,
)


class OperationalMeasurementCaptureError(ValueError):
    """Raised when operational measurement capture fails closed."""


FORBIDDEN_INPUT_FIELDS = frozenset(
    {
        "name",
        "full_name",
        "first_name",
        "last_name",
        "email",
        "email_address",
        "phone",
        "phone_number",
        "mobile",
        "address",
        "street_address",
        "postcode",
        "postal_code",
        "ip_address",
        "device_id",
        "cookie",
        "customer_name",
        "customer_email",
        "customer_phone",
        "raw_customer_record",
        "raw_quote",
        "full_transcript",
        "recording",
    }
)
PLACEHOLDER_MARKERS = (
    "placeholder",
    "replace_with",
    "replace with",
    "manual_test",
    "dummy",
    "sample answer",
    "lorem ipsum",
)
EMAIL_PATTERN = re.compile(
    r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b",
    re.IGNORECASE,
)
PHONE_PATTERN = re.compile(
    r"(?<!\d)(?:\+?\d[\s().-]*){10,15}(?!\d)"
)
TOKEN_PATTERN = re.compile(r"^[A-Za-z0-9_.:-]{3,120}$")


class OperationalMeasurementCaptureService:
    """Validate measurements and append only sanitized candidates."""

    SCHEMA_VERSION = "STAGE4G-0.2"
    POLICY_ROOT = Path("config")
    REPORT_ROOT = Path(
        "reports/research/operational_measurement_capture"
    )

    def __init__(
        self,
        *,
        candidate_store: (
            OperationalMeasurementCandidateStore | None
        ) = None,
        capture_registry: (
            OperationalMeasurementCaptureRegistry | None
        ) = None,
    ) -> None:
        self.project_root = Path.cwd().resolve()
        self.policy_root = (
            self.project_root / self.POLICY_ROOT
        ).resolve()
        self.report_root = (
            self.project_root / self.REPORT_ROOT
        ).resolve()
        self.candidate_store = (
            candidate_store
            or OperationalMeasurementCandidateStore()
        )
        self.capture_registry = (
            capture_registry
            or OperationalMeasurementCaptureRegistry()
        )

    def capture(
        self,
        *,
        input_file: str | Path,
        policy_file: str | Path,
        output_file: str | Path,
    ) -> dict[str, Any]:
        input_path = Path(input_file).resolve()
        if not input_path.is_file():
            raise OperationalMeasurementCaptureError(
                f"Measurement input does not exist: {input_file}"
            )
        policy_path = self._controlled_file(
            Path(policy_file),
            root=self.policy_root,
            suffix=".json",
            label="measurement policy",
        )
        output_path = self._controlled_output(
            Path(output_file),
            root=self.report_root,
            suffix=".json",
            label="capture report",
        )
        if output_path.exists():
            raise OperationalMeasurementCaptureError(
                "Capture report already exists and will not be "
                "overwritten"
            )

        policy = self._load_object(policy_path)
        measurements = self._load_measurements(input_path)
        campaign_id = self._required_text(
            "campaign_id",
            policy.get("campaign_id", ""),
        )
        policy_id = self._required_text(
            "policy_id",
            policy.get("policy_id", ""),
        )
        program_id = self._required_text(
            "measurement_program_id",
            policy.get("measurement_program_id", ""),
        )
        input_hash = self._file_hash(input_path)
        policy_hash = self._file_hash(policy_path)
        batch_id = self._batch_id(
            program_id,
            input_hash,
            policy_hash,
        )
        if self.capture_registry.has_batch(batch_id):
            raise OperationalMeasurementCaptureError(
                "This measurement batch has already been processed"
            )

        candidate_path = self.candidate_store.path_for(program_id)
        existing = self.candidate_store.read(candidate_path)
        measurement_ids = {
            str(record.get("measurement_id", ""))
            for record in existing
        }
        fingerprints = {
            str(record.get("measurement_fingerprint", ""))
            for record in existing
        }
        source_references = {
            str(record.get("source_reference", ""))
            for record in existing
        }

        accepted: list[dict[str, Any]] = []
        blocked: list[dict[str, Any]] = []
        for index, raw in enumerate(measurements, start=1):
            candidate, reasons = self._candidate(
                raw=raw,
                index=index,
                policy=policy,
                policy_hash=policy_hash,
            )
            if candidate is not None:
                if candidate["measurement_id"] in measurement_ids:
                    reasons.append("duplicate_measurement_id")
                if (
                    candidate["measurement_fingerprint"]
                    in fingerprints
                ):
                    reasons.append(
                        "duplicate_measurement_fingerprint"
                    )
                if (
                    candidate["source_reference"]
                    in source_references
                ):
                    reasons.append("duplicate_source_reference")

            reasons = list(dict.fromkeys(reasons))
            if candidate is None or reasons:
                blocked.append(
                    {
                        "input_index": index,
                        "measurement_id": (
                            str(raw.get("measurement_id", ""))
                            if isinstance(raw, dict)
                            else ""
                        ),
                        "blocking_reasons": reasons
                        or ["measurement_not_an_object"],
                    }
                )
                continue

            accepted.append(candidate)
            measurement_ids.add(candidate["measurement_id"])
            fingerprints.add(
                candidate["measurement_fingerprint"]
            )
            source_references.add(candidate["source_reference"])

        candidate_snapshot = ControlledMeasurementStore.snapshot(
            candidate_path
        )
        registry_snapshot = ControlledMeasurementStore.snapshot(
            self.capture_registry.registry_path
        )
        try:
            self.candidate_store.append_many(
                candidate_path,
                accepted,
            )
            report = {
                "batch_id": batch_id,
                "campaign_id": campaign_id,
                "measurement_program_id": program_id,
                "policy_id": policy_id,
                "policy_path": self._project_path(policy_path),
                "policy_hash": policy_hash,
                "input_path": self._project_path(input_path),
                "input_hash": input_hash,
                "candidate_path": self._project_path(
                    candidate_path
                ),
                "received": len(measurements),
                "accepted": len(accepted),
                "blocked": len(blocked),
                "blocked_measurements": blocked,
                "taxonomy_status": (
                    "separate_operational_measurement"
                ),
                "validation_log_import_allowed": False,
                "captured_at": datetime.now(UTC).isoformat(),
                "protected_actions": {
                    "validation_evidence_log_modified": False,
                    "theme_state_modified": False,
                    "build_approved": False,
                    "public_action_taken": False,
                    "automatic_outreach": False,
                },
            }
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(
                json.dumps(
                    report,
                    indent=2,
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )
            self.capture_registry.append_many(
                self.capture_registry.registry_path,
                [
                    {
                        "batch_id": batch_id,
                        "campaign_id": campaign_id,
                        "measurement_program_id": program_id,
                        "accepted": len(accepted),
                        "blocked": len(blocked),
                        "candidate_path": self._project_path(
                            candidate_path
                        ),
                        "report_path": self._project_path(
                            output_path
                        ),
                        "captured_at": report["captured_at"],
                    }
                ],
            )
            return report
        except Exception:
            ControlledMeasurementStore.restore(
                candidate_path,
                candidate_snapshot,
            )
            ControlledMeasurementStore.restore(
                self.capture_registry.registry_path,
                registry_snapshot,
            )
            if output_path.exists():
                output_path.unlink()
            raise

    def _candidate(
        self,
        *,
        raw: Any,
        index: int,
        policy: dict[str, Any],
        policy_hash: str,
    ) -> tuple[dict[str, Any] | None, list[str]]:
        if not isinstance(raw, dict):
            return None, ["measurement_not_an_object"]
        reasons: list[str] = []
        forbidden = sorted(
            str(key)
            for key in raw
            if str(key).strip().lower()
            in FORBIDDEN_INPUT_FIELDS
        )
        if forbidden:
            reasons.append(
                "forbidden_fields:" + ",".join(forbidden)
            )

        values = {
            "campaign_id": str(
                raw.get("campaign_id", "")
            ).strip(),
            "measurement_program_id": str(
                raw.get("measurement_program_id", "")
            ).strip(),
            "measurement_id": str(
                raw.get("measurement_id", "")
            ).strip(),
            "pilot_id": str(raw.get("pilot_id", "")).strip(),
            "metric_name": str(
                raw.get("metric_name", "")
            ).strip().lower(),
            "comparison_method": str(
                raw.get("comparison_method", "")
            ).strip().lower(),
            "operational_context_summary": " ".join(
                str(
                    raw.get("operational_context_summary", "")
                ).split()
            ),
            "expert_interpretation": " ".join(
                str(raw.get("expert_interpretation", "")).split()
            ),
            "decision_taken": str(
                raw.get("decision_taken", "")
            ).strip().lower(),
            "source_reference": str(
                raw.get("source_reference", "")
            ).strip(),
            "attestor_reference": str(
                raw.get("attestor_reference", "")
            ).strip(),
        }
        for field_name, value in values.items():
            if not value:
                reasons.append(f"{field_name}_missing")

        if values["campaign_id"] != str(
            policy.get("campaign_id", "")
        ):
            reasons.append("campaign_id_mismatch")
        if values["measurement_program_id"] != str(
            policy.get("measurement_program_id", "")
        ):
            reasons.append("measurement_program_id_mismatch")
        for field_name in (
            "measurement_id",
            "pilot_id",
            "source_reference",
            "attestor_reference",
        ):
            value = values[field_name]
            if value and not TOKEN_PATTERN.fullmatch(value):
                reasons.append(f"{field_name}_invalid")

        narrative_fields = (
            "operational_context_summary",
            "expert_interpretation",
        )
        for field_name in narrative_fields:
            text = values[field_name]
            if len(text) < 30:
                reasons.append(f"{field_name}_too_short")
            if len(text) > 1_200:
                reasons.append(f"{field_name}_too_long")
            if EMAIL_PATTERN.search(text):
                reasons.append(f"email_detected_in_{field_name}")
            if PHONE_PATTERN.search(text):
                reasons.append(f"phone_detected_in_{field_name}")
            if any(
                marker in text.lower()
                for marker in PLACEHOLDER_MARKERS
            ):
                reasons.append(
                    f"placeholder_marker_in_{field_name}"
                )
        if bool(raw.get("synthetic_measurement", False)):
            reasons.append("synthetic_measurement_not_allowed")
        if raw.get("provenance_attested") is not True:
            reasons.append("provenance_attestation_required")

        metric_definitions = policy.get("metrics")
        metric_definition = (
            metric_definitions.get(values["metric_name"])
            if isinstance(metric_definitions, dict)
            else None
        )
        if not isinstance(metric_definition, dict):
            reasons.append("metric_name_not_allowed")
            metric_definition = {}

        comparison_methods = {
            str(value).lower()
            for value in policy.get(
                "allowed_comparison_methods",
                [],
            )
        }
        if values["comparison_method"] not in comparison_methods:
            reasons.append("comparison_method_not_allowed")
        decisions = {
            str(value).lower()
            for value in policy.get(
                "allowed_decisions",
                [],
            )
        }
        if values["decision_taken"] not in decisions:
            reasons.append("decision_taken_not_allowed")

        baseline_start = self._date_value(
            raw.get("baseline_start"),
            "baseline_start",
            reasons,
        )
        baseline_end = self._date_value(
            raw.get("baseline_end"),
            "baseline_end",
            reasons,
        )
        intervention_start = self._date_value(
            raw.get("intervention_start"),
            "intervention_start",
            reasons,
        )
        observation_end = self._date_value(
            raw.get("observation_end"),
            "observation_end",
            reasons,
        )
        if (
            baseline_start is not None
            and baseline_end is not None
            and intervention_start is not None
            and observation_end is not None
        ):
            if not (
                baseline_start <= baseline_end
                < intervention_start <= observation_end
            ):
                reasons.append("measurement_period_order_invalid")
            baseline_days = (
                baseline_end - baseline_start
            ).days + 1
            observation_days = (
                observation_end - intervention_start
            ).days + 1
            if baseline_days < int(
                policy.get("minimum_baseline_days", 1)
            ):
                reasons.append("baseline_period_too_short")
            if observation_days < int(
                policy.get("minimum_observation_days", 1)
            ):
                reasons.append("observation_period_too_short")
        else:
            baseline_days = 0
            observation_days = 0

        baseline_sample_size = self._integer_value(
            raw.get("baseline_sample_size"),
            "baseline_sample_size",
            reasons,
            minimum=1,
        )
        observation_sample_size = self._integer_value(
            raw.get("observation_sample_size"),
            "observation_sample_size",
            reasons,
            minimum=1,
        )
        minimum_sample = int(
            policy.get("minimum_sample_size", 1)
        )
        if (
            baseline_sample_size is not None
            and baseline_sample_size < minimum_sample
        ):
            reasons.append("baseline_sample_size_too_small")
        if (
            observation_sample_size is not None
            and observation_sample_size < minimum_sample
        ):
            reasons.append("observation_sample_size_too_small")

        outcome_before = self._number_value(
            raw.get("outcome_before"),
            "outcome_before",
            reasons,
        )
        outcome_after = self._number_value(
            raw.get("outcome_after"),
            "outcome_after",
            reasons,
        )
        persistence_days = self._integer_value(
            raw.get("persistence_period_days"),
            "persistence_period_days",
            reasons,
            minimum=0,
        )
        if (
            persistence_days is not None
            and observation_days
            and persistence_days > observation_days
        ):
            reasons.append(
                "persistence_period_exceeds_observation"
            )

        estimated_financial_effect = self._optional_number(
            raw.get("estimated_financial_effect_gbp"),
            "estimated_financial_effect_gbp",
            reasons,
        )
        manual_before = self._optional_number(
            raw.get("manual_time_before_minutes"),
            "manual_time_before_minutes",
            reasons,
            minimum=0,
        )
        manual_after = self._optional_number(
            raw.get("manual_time_after_minutes"),
            "manual_time_after_minutes",
            reasons,
            minimum=0,
        )
        if (manual_before is None) != (manual_after is None):
            reasons.append("manual_time_pair_required")

        context_codes = self._code_list(
            raw.get("operational_context_codes"),
            field_name="operational_context_codes",
            allowed=policy.get(
                "allowed_operational_context_codes",
                [],
            ),
            reasons=reasons,
            required=True,
        )
        confounders = self._code_list(
            raw.get("known_confounders"),
            field_name="known_confounders",
            allowed=policy.get(
                "allowed_confounder_codes",
                [],
            ),
            reasons=reasons,
            required=True,
        )
        if "none_known" in confounders and len(confounders) > 1:
            reasons.append("none_known_cannot_mix_with_confounders")
        feedback_codes = self._code_list(
            raw.get("feedback_reason_codes", []),
            field_name="feedback_reason_codes",
            allowed=policy.get(
                "allowed_feedback_reason_codes",
                [],
            ),
            reasons=reasons,
            required=False,
        )
        unintended_codes = self._code_list(
            raw.get("unintended_effect_codes", []),
            field_name="unintended_effect_codes",
            allowed=policy.get(
                "allowed_unintended_effect_codes",
                [],
            ),
            reasons=reasons,
            required=False,
        )

        if reasons:
            return None, reasons

        if (
            baseline_start is None
            or baseline_end is None
            or intervention_start is None
            or observation_end is None
            or baseline_sample_size is None
            or observation_sample_size is None
            or outcome_before is None
            or outcome_after is None
            or persistence_days is None
        ):
            raise OperationalMeasurementCaptureError(
                "Measurement passed validation without all required "
                "parsed values"
            )

        change = outcome_after - outcome_before
        relative_change = (
            (change / abs(outcome_before)) * 100
            if outcome_before != 0
            else None
        )
        materiality_threshold = float(
            metric_definition.get("materiality_threshold", 0)
        )
        improvement_direction = str(
            metric_definition.get("improvement_direction", "")
        ).lower()
        effect_direction = self._effect_direction(
            change=change,
            threshold=materiality_threshold,
            improvement_direction=improvement_direction,
        )
        manual_time_change = (
            manual_after - manual_before
            if manual_before is not None
            and manual_after is not None
            else None
        )

        candidate = {
            "schema_version": self.SCHEMA_VERSION,
            "policy_id": str(policy.get("policy_id", "")),
            "policy_hash": policy_hash,
            "campaign_id": values["campaign_id"],
            "measurement_program_id": values[
                "measurement_program_id"
            ],
            "measurement_id": values["measurement_id"],
            "pilot_id": values["pilot_id"],
            "metric_name": values["metric_name"],
            "metric_unit": str(
                metric_definition.get("unit", "")
            ),
            "improvement_direction": improvement_direction,
            "comparison_method": values["comparison_method"],
            "baseline_start": baseline_start.isoformat(),
            "baseline_end": baseline_end.isoformat(),
            "intervention_start": intervention_start.isoformat(),
            "observation_end": observation_end.isoformat(),
            "baseline_duration_days": baseline_days,
            "observation_duration_days": observation_days,
            "baseline_sample_size": baseline_sample_size,
            "observation_sample_size": observation_sample_size,
            "operational_context_codes": context_codes,
            "operational_context_summary": values[
                "operational_context_summary"
            ],
            "known_confounders": confounders,
            "outcome_before": outcome_before,
            "outcome_after": outcome_after,
            "absolute_change": change,
            "relative_change_percent": relative_change,
            "effect_magnitude": abs(change),
            "effect_direction": effect_direction,
            "materiality_threshold": materiality_threshold,
            "persistence_period_days": persistence_days,
            "estimated_financial_effect_gbp": (
                estimated_financial_effect
            ),
            "manual_time_before_minutes": manual_before,
            "manual_time_after_minutes": manual_after,
            "manual_time_change_minutes": manual_time_change,
            "feedback_reason_codes": feedback_codes,
            "unintended_effect_codes": unintended_codes,
            "expert_interpretation": values[
                "expert_interpretation"
            ],
            "decision_taken": values["decision_taken"],
            "source_reference": values["source_reference"],
            "captured_at": self._iso_datetime(
                raw.get("captured_at", "")
            ),
            "provenance_attested": True,
            "attestor_reference": values[
                "attestor_reference"
            ],
            "claim_boundary": "observational_not_causal",
            "taxonomy_status": (
                "separate_operational_measurement"
            ),
            "validation_log_import_allowed": False,
            "human_review_required": True,
            "received_at": datetime.now(UTC).isoformat(),
            "input_index": index,
        }
        candidate["measurement_fingerprint"] = (
            self._payload_hash(
                {
                    "measurement_program_id": candidate[
                        "measurement_program_id"
                    ],
                    "pilot_id": candidate["pilot_id"],
                    "metric_name": candidate["metric_name"],
                    "baseline_start": candidate[
                        "baseline_start"
                    ],
                    "observation_end": candidate[
                        "observation_end"
                    ],
                    "outcome_before": candidate[
                        "outcome_before"
                    ],
                    "outcome_after": candidate[
                        "outcome_after"
                    ],
                }
            )
        )
        candidate["candidate_hash"] = self._payload_hash(candidate)
        return candidate, []

    @staticmethod
    def _effect_direction(
        *,
        change: float,
        threshold: float,
        improvement_direction: str,
    ) -> str:
        if abs(change) <= threshold:
            return "no_material_change"
        if improvement_direction == "increase_is_better":
            return "improvement" if change > 0 else "deterioration"
        if improvement_direction == "decrease_is_better":
            return "improvement" if change < 0 else "deterioration"
        raise OperationalMeasurementCaptureError(
            "Metric improvement_direction must be increase_is_better "
            "or decrease_is_better"
        )

    @classmethod
    def _date_value(
        cls,
        value: Any,
        field_name: str,
        reasons: list[str],
    ) -> date | None:
        if not isinstance(value, str) or not value.strip():
            reasons.append(f"{field_name}_missing")
            return None
        try:
            return date.fromisoformat(value.strip())
        except ValueError:
            reasons.append(f"{field_name}_invalid")
            return None

    @staticmethod
    def _integer_value(
        value: Any,
        field_name: str,
        reasons: list[str],
        *,
        minimum: int,
    ) -> int | None:
        if (
            not isinstance(value, int)
            or isinstance(value, bool)
            or value < minimum
        ):
            reasons.append(f"{field_name}_invalid")
            return None
        return value

    @staticmethod
    def _number_value(
        value: Any,
        field_name: str,
        reasons: list[str],
    ) -> float | None:
        if (
            not isinstance(value, (int, float))
            or isinstance(value, bool)
            or not math.isfinite(float(value))
        ):
            reasons.append(f"{field_name}_invalid")
            return None
        return float(value)

    @classmethod
    def _optional_number(
        cls,
        value: Any,
        field_name: str,
        reasons: list[str],
        *,
        minimum: float | None = None,
    ) -> float | None:
        if value in (None, ""):
            return None
        number = cls._number_value(value, field_name, reasons)
        if (
            number is not None
            and minimum is not None
            and number < minimum
        ):
            reasons.append(f"{field_name}_below_minimum")
            return None
        return number

    @staticmethod
    def _code_list(
        value: Any,
        *,
        field_name: str,
        allowed: Any,
        reasons: list[str],
        required: bool,
    ) -> list[str]:
        if not isinstance(value, list):
            reasons.append(f"{field_name}_must_be_list")
            return []
        codes = [
            str(item).strip().lower()
            for item in value
            if str(item).strip()
        ]
        if required and not codes:
            reasons.append(f"{field_name}_required")
        if len(codes) != len(set(codes)):
            reasons.append(f"{field_name}_contains_duplicates")
        allowed_codes = {
            str(item).strip().lower()
            for item in allowed
        }
        unsupported = sorted(set(codes) - allowed_codes)
        if unsupported:
            reasons.append(
                f"{field_name}_unsupported:"
                + ",".join(unsupported)
            )
        return codes

    @staticmethod
    def _load_measurements(path: Path) -> list[Any]:
        if path.suffix == ".jsonl":
            records: list[Any] = []
            for line_number, line in enumerate(
                path.read_text(encoding="utf-8").splitlines(),
                start=1,
            ):
                if not line.strip():
                    continue
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError as exc:
                    raise OperationalMeasurementCaptureError(
                        "Measurement JSONL is invalid at line "
                        f"{line_number}"
                    ) from exc
            return records
        if path.suffix != ".json":
            raise OperationalMeasurementCaptureError(
                "Measurement input must be .json or .jsonl"
            )
        try:
            payload = json.loads(
                path.read_text(encoding="utf-8")
            )
        except json.JSONDecodeError as exc:
            raise OperationalMeasurementCaptureError(
                "Measurement JSON is invalid"
            ) from exc
        if isinstance(payload, list):
            return payload
        if isinstance(payload, dict):
            measurements = payload.get("measurements")
            if isinstance(measurements, list):
                return measurements
            return [payload]
        raise OperationalMeasurementCaptureError(
            "Measurement JSON must be an object or list"
        )

    @staticmethod
    def _batch_id(
        program_id: str,
        input_hash: str,
        policy_hash: str,
    ) -> str:
        material = (
            f"{program_id}|{input_hash}|{policy_hash}"
        ).encode()
        return (
            "OMCB-"
            + hashlib.sha256(material).hexdigest()[:20]
        )

    @staticmethod
    def _payload_hash(payload: dict[str, Any]) -> str:
        encoded = json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode()
        return hashlib.sha256(encoded).hexdigest()

    @staticmethod
    def _file_hash(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(
                lambda: handle.read(65_536),
                b"",
            ):
                digest.update(chunk)
        return digest.hexdigest()

    @staticmethod
    def _load_object(path: Path) -> dict[str, Any]:
        try:
            payload = json.loads(
                path.read_text(encoding="utf-8")
            )
        except (OSError, json.JSONDecodeError) as exc:
            raise OperationalMeasurementCaptureError(
                f"Could not read JSON object: {path}"
            ) from exc
        if not isinstance(payload, dict):
            raise OperationalMeasurementCaptureError(
                "JSON file must contain an object"
            )
        return payload

    def _controlled_file(
        self,
        path: Path,
        *,
        root: Path,
        suffix: str,
        label: str,
    ) -> Path:
        resolved = path.resolve()
        if not self._is_within(resolved, root):
            raise OperationalMeasurementCaptureError(
                f"{label} must stay inside {self._project_path(root)}"
            )
        if resolved.suffix != suffix:
            raise OperationalMeasurementCaptureError(
                f"{label} must use {suffix}"
            )
        if not resolved.is_file():
            raise OperationalMeasurementCaptureError(
                f"{label} does not exist: {path}"
            )
        return resolved

    def _controlled_output(
        self,
        path: Path,
        *,
        root: Path,
        suffix: str,
        label: str,
    ) -> Path:
        resolved = path.resolve()
        if not self._is_within(resolved, root):
            raise OperationalMeasurementCaptureError(
                f"{label} must stay inside {self._project_path(root)}"
            )
        if resolved.suffix != suffix:
            raise OperationalMeasurementCaptureError(
                f"{label} must use {suffix}"
            )
        return resolved

    def _project_path(self, path: Path) -> str:
        try:
            return str(
                path.resolve().relative_to(self.project_root)
            )
        except ValueError as exc:
            raise OperationalMeasurementCaptureError(
                "Path is outside the project root"
            ) from exc

    @staticmethod
    def _is_within(path: Path, root: Path) -> bool:
        try:
            path.relative_to(root)
            return True
        except ValueError:
            return False

    @staticmethod
    def _required_text(field_name: str, value: Any) -> str:
        if not isinstance(value, str) or not value.strip():
            raise OperationalMeasurementCaptureError(
                f"{field_name} is required"
            )
        return " ".join(value.split())

    @staticmethod
    def _iso_datetime(value: Any) -> str:
        if not isinstance(value, str) or not value.strip():
            raise OperationalMeasurementCaptureError(
                "captured_at is required"
            )
        normalized = value.strip().replace("Z", "+00:00")
        try:
            parsed = datetime.fromisoformat(normalized)
        except ValueError as exc:
            raise OperationalMeasurementCaptureError(
                "captured_at must be ISO-8601"
            ) from exc
        if parsed.tzinfo is None:
            raise OperationalMeasurementCaptureError(
                "captured_at must include a timezone"
            )
        return parsed.astimezone(UTC).isoformat()
