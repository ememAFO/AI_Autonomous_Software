from dataclasses import dataclass, field
from enum import StrEnum


class PainCategory(StrEnum):
    WORKFLOW = "workflow"
    ECONOMIC = "economic"
    TIME = "time"
    INTEGRATION = "integration"
    SUPPORT = "support"
    ONBOARDING = "onboarding"
    UX_FRICTION = "ux_friction"
    COMPLIANCE_RISK = "compliance_risk"
    COMMUNICATION = "communication"
    RETENTION = "retention"
    UNCLEAR = "unclear"


class CommercialSignal(StrEnum):
    STRONG = "strong"
    MODERATE = "moderate"
    WEAK = "weak"


class PainDecision(StrEnum):
    ACCEPT = "ACCEPT"
    WEAK_PAIN = "WEAK_PAIN"
    REJECT = "REJECT"


@dataclass(frozen=True)
class ProcessMap:
    trigger: str
    action: str
    friction: str
    consequence: str
    workaround: str | None = None


@dataclass(frozen=True)
class PainAnalysis:
    is_pain: bool
    decision: PainDecision
    confidence: float
    pain_category: PainCategory
    commercial_signal: CommercialSignal
    current_state: str
    desired_state: str
    gap: str
    consequence: str
    symptom: str
    possible_root_causes: list[str] = field(default_factory=list)
    evidence: list[str] = field(default_factory=list)
    process_map: ProcessMap | None = None
    notes: list[str] = field(default_factory=list)
