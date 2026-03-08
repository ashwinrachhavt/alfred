from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class SourceProvider(str, Enum):
    """Known upstream sources for company culture insights."""

    glassdoor = "glassdoor"
    blind = "blind"
    levels = "levels"
    web = "web"


class SentimentLabel(str, Enum):
    positive = "positive"
    neutral = "neutral"
    negative = "negative"
    mixed = "mixed"


class SourceInfo(BaseModel):
    """Metadata for a crawled/queried source used to build the report."""

    provider: SourceProvider = Field(..., description="Upstream provider identifier.")
    url: str | None = Field(default=None, description="Source URL, when applicable.")
    title: str | None = Field(default=None, description="Source page title, when applicable.")
    error: str | None = Field(
        default=None,
        description="Non-fatal error encountered while fetching or parsing this source.",
    )


class Review(BaseModel):
    """A single employee review entry (normalized)."""

    source: SourceProvider = Field(..., description="Upstream provider.")
    source_url: str | None = Field(default=None, description="Link to the review page.")
    rating: float | None = Field(default=None, description="Overall rating, typically 1-5.")
    title: str | None = Field(default=None, description="Review headline/title.")
    summary: str | None = Field(default=None, description="Short summary of the review.")
    pros: list[str] = Field(default_factory=list, description="Pros bullet points.")
    cons: list[str] = Field(default_factory=list, description="Cons bullet points.")
    job_title: str | None = Field(
        default=None, description="Role/position of reviewer, if available."
    )
    location: str | None = Field(default=None, description="Location of reviewer, if available.")
    employment_status: str | None = Field(
        default=None, description="e.g., Current Employee, Former Employee."
    )
    review_date: str | None = Field(
        default=None,
        description="Review date in ISO format when available (UTC recommended).",
    )


class InterviewExperience(BaseModel):
    """A single interview experience entry (normalized)."""

    source: SourceProvider = Field(..., description="Upstream provider.")
    source_url: str | None = Field(default=None, description="Link to the interview post/page.")
    role: str | None = Field(default=None, description="Interviewed role or job title.")
    location: str | None = Field(default=None, description="Interview location, if available.")
    interview_date: str | None = Field(default=None, description="ISO date when available.")
    difficulty: str | None = Field(default=None, description="Difficulty label when available.")
    outcome: str | None = Field(default=None, description="Outcome label when available.")
    process_summary: str | None = Field(
        default=None, description="Short description of process."
    )
    questions: list[str] = Field(default_factory=list, description="Notable questions asked.")


class SalaryRange(BaseModel):
    """A compensation range (values may be partial)."""

    currency: str | None = Field(default=None, description="Currency code, e.g., USD.")
    period: str | None = Field(default=None, description="e.g., YEAR, MONTH.")
    base_min: float | None = Field(default=None)
    base_max: float | None = Field(default=None)
    base_median: float | None = Field(default=None)
    total_min: float | None = Field(default=None)
    total_max: float | None = Field(default=None)
    total_median: float | None = Field(default=None)


class SalaryData(BaseModel):
    """Salary/compensation data for a company and role (normalized)."""

    source: SourceProvider = Field(..., description="Upstream provider.")
    source_url: str | None = Field(default=None, description="Link to the salary page.")
    role: str | None = Field(default=None, description="Role/title this range applies to.")
    location: str | None = Field(default=None, description="Location/geo, if available.")
    level: str | None = Field(default=None, description="Level, if available (e.g., L5).")
    range: SalaryRange = Field(default_factory=SalaryRange)


class DiscussionPost(BaseModel):
    """A public discussion post (Blind or other sources)."""

    source: SourceProvider = Field(..., description="Upstream provider.")
    url: str | None = Field(default=None, description="Post URL.")
    title: str | None = Field(default=None, description="Post title.")
    excerpt: str | None = Field(default=None, description="Short excerpt/snippet.")
    created_at: str | None = Field(default=None, description="ISO datetime when available.")
    tags: list[str] = Field(
        default_factory=list, description="Any tags/keywords surfaced from the post."
    )


class CultureSignals(BaseModel):
    """Aggregated qualitative signals derived from the extracted corpus."""

    culture_keywords: list[str] = Field(
        default_factory=list, description="Distinct culture keywords."
    )
    sentiment: SentimentLabel = Field(default=SentimentLabel.neutral)
    work_life_balance_indicators: list[str] = Field(
        default_factory=list,
        description="Short WLB indicators (e.g., 'late nights', 'flexible hours').",
    )
    management_rating: float | None = Field(
        default=None, description="Estimated management rating if available (1-5)."
    )
    management_notes: str | None = Field(
        default=None, description="Short qualitative management signal summary."
    )


class CompanyInsightsReport(BaseModel):
    """Unified company culture insights report stored in Mongo and returned by the API."""

    company: str
    generated_at: str = Field(..., description="UTC ISO timestamp when the report was generated.")
    sources: list[SourceInfo] = Field(default_factory=list)
    reviews: list[Review] = Field(default_factory=list)
    interviews: list[InterviewExperience] = Field(default_factory=list)
    salaries: list[SalaryData] = Field(default_factory=list)
    posts: list[DiscussionPost] = Field(default_factory=list)
    signals: CultureSignals = Field(default_factory=CultureSignals)
    warnings: list[str] = Field(
        default_factory=list, description="Non-fatal warnings / coverage notes."
    )
