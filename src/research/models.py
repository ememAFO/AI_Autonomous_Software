from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum


class OpportunitySource(StrEnum):
    REDDIT = "reddit"
    GITHUB = "github"
    REVIEW_SITE = "review_site"
    FORUM = "forum"
    SUPPORT_THREAD = "support_thread"
    MANUAL = "manual"


@dataclass(frozen=True)
class Opportunity:
    title: str
    pain_point: str
    source: OpportunitySource
    industry: str
    frequency: float
    urgency: float
    monetization: float
    retention_impact: float
    competition_gap: float
    automation_potential: float
    implementation_difficulty: float
    evidence: list[str] = field(default_factory=list)
    suggested_mvp: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        required_text_fields = {
            "title": self.title,
            "pain_point": self.pain_point,
            "industry": self.industry,
        }

        for field_name, value in required_text_fields.items():
            if not value or not value.strip():
                raise ValueError(f"{field_name} cannot be empty")

        score_fields = {
            "frequency": self.frequency,
            "urgency": self.urgency,
            "monetization": self.monetization,
            "retention_impact": self.retention_impact,
            "competition_gap": self.competition_gap,
            "automation_potential": self.automation_potential,
            "implementation_difficulty": self.implementation_difficulty,
        }

        for field_name, value in score_fields.items():
            if value < 0 or value > 10:
                raise ValueError(f"{field_name} must be between 0 and 10")
