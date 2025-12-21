from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Annotated, Optional

from pydantic import BaseModel, Field
from pydantic.types import conint

from alfred.schemas.company_insights import SentimentLabel

Score0To100 = Annotated[conint(ge=0, le=100), Field(description="Score in [0, 100].")]


class CultureDimension(str, Enum):
    """A small, opinionated set of culture/value dimensions for matching.

    These are used to build a stable radar chart and keep scoring predictable.
    """

    autonomy = "autonomy"
    collaboration = "collaboration"
    structure = "structure"
    pace = "pace"
    learning = "learning"
    work_life_balance = "work_life_balance"
    feedback = "feedback"
    mission = "mission"


DEFAULT_DIMENSIONS: tuple[CultureDimension, ...] = (
    CultureDimension.autonomy,
    CultureDimension.collaboration,
    CultureDimension.structure,
    CultureDimension.pace,
    CultureDimension.learning,
    CultureDimension.work_life_balance,
    CultureDimension.feedback,
    CultureDimension.mission,
)


class CultureVector(BaseModel):
    """A normalized vector of culture/value scores by dimension."""

    dimensions: dict[CultureDimension, Score0To100] = Field(default_factory=dict)

    def normalized(self, *, default_value: int = 50) -> dict[CultureDimension, int]:
        """Return a dense vector, filling missing dimensions with `default_value`."""
        out: dict[CultureDimension, int] = {}
        for dim in DEFAULT_DIMENSIONS:
            raw = self.dimensions.get(dim)
            out[dim] = int(raw if raw is not None else default_value)
        return out


class UserValuesProfile(BaseModel):
    """A user's stable preference profile."""

    values: CultureVector = Field(default_factory=CultureVector)
    notes: Optional[str] = Field(default=None, description="Optional free-form context.")


class CompanyCultureProfile(BaseModel):
    """A company culture estimate derived from public signals and/or provided snippets."""

    culture: CultureVector = Field(default_factory=CultureVector)
    keywords: list[str] = Field(
        default_factory=list,
        description="Distinct culture keywords surfaced from the corpus.",
    )
    sentiment: SentimentLabel = Field(default=SentimentLabel.neutral)
    evidence_excerpts: list[str] = Field(
        default_factory=list,
        description="Short excerpts supporting the inferred culture profile.",
    )


class FitDimensionScore(BaseModel):
    """Per-dimension alignment details."""

    dimension: CultureDimension
    user: Score0To100
    company: Score0To100
    score: Score0To100 = Field(..., description="Alignment score for this dimension.")
    delta: int = Field(..., description="Signed delta (company - user) in points.")


class FitScoreBreakdown(BaseModel):
    """Overall alignment with per-dimension breakdown."""

    overall: Score0To100
    by_dimension: list[FitDimensionScore] = Field(default_factory=list)


class TalkingPointType(str, Enum):
    strength = "strength"
    risk = "risk"
    question = "question"


class TalkingPoint(BaseModel):
    """A human-friendly talking point to use in interviews."""

    type: TalkingPointType
    dimension: CultureDimension | None = None
    title: str
    detail: str


class RadarChartData(BaseModel):
    """JSON-friendly radar chart payload.

    Frontends can render this as a radar/spider chart, but the API keeps it model-agnostic.
    """

    labels: list[str]
    user_values: list[Score0To100]
    company_values: list[Score0To100]


class CultureFitProfileUpsert(BaseModel):
    """Create/update a user's culture preferences.

    `values` is a dimension -> score map. Missing dimensions default to 50.
    """

    user_id: str | None = Field(default=None, description="Optional user identifier.")
    values: dict[CultureDimension, Score0To100] = Field(default_factory=dict)
    notes: str | None = None


class CultureFitProfileRecord(BaseModel):
    """Stored user values profile."""

    id: str
    user_id: str
    profile: UserValuesProfile
    created_at: datetime
    updated_at: datetime


class CultureFitAnalyzeRequest(BaseModel):
    """Run culture fit analysis for a company given a saved or inline user profile."""

    user_id: str | None = Field(default=None, description="Optional user identifier.")
    company: str = Field(..., description="Company name.")
    role: str | None = Field(default=None, description="Optional role/context.")

    # Optional: allow caller to provide their own corpora.
    reviews: list[str] = Field(default_factory=list, description="Employee review snippets.")
    discussions: list[str] = Field(default_factory=list, description="Forum/discussion snippets.")

    # Optional: fetch from existing sources (Glassdoor/Blind) via CompanyInsights cache/service.
    fetch_company_insights: bool = Field(
        default=True,
        description="When true, pulls corpora from /company/insights sources (cached).",
    )
    refresh: bool = Field(default=False, description="Force refresh of company insights.")

    # Optional: inline profile override for one-off analysis.
    user_profile: UserValuesProfile | None = None


class CultureFitAnalysisResult(BaseModel):
    """Full culture fit analysis output."""

    company: str
    role: str | None = None
    user_profile: UserValuesProfile
    company_profile: CompanyCultureProfile
    fit: FitScoreBreakdown
    radar: RadarChartData
    talking_points: list[TalkingPoint] = Field(default_factory=list)


__all__ = [
    "CultureDimension",
    "CultureFitAnalysisResult",
    "CultureFitAnalyzeRequest",
    "CultureFitProfileRecord",
    "CultureFitProfileUpsert",
    "CultureVector",
    "DEFAULT_DIMENSIONS",
    "FitDimensionScore",
    "FitScoreBreakdown",
    "RadarChartData",
    "TalkingPoint",
    "TalkingPointType",
    "UserValuesProfile",
    "CompanyCultureProfile",
]
