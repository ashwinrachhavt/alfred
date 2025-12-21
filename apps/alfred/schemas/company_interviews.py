from __future__ import annotations

from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class InterviewProvider(str, Enum):
    glassdoor = "glassdoor"
    blind = "blind"


class CompanyInterviewExperience(BaseModel):
    """Canonical record stored for a single interview experience."""

    company: str = Field(..., description="Company name used for indexing/search.")
    provider: InterviewProvider = Field(..., description="Upstream provider.")
    source_id: str = Field(..., description="Stable unique identifier for de-duplication.")
    source_url: Optional[str] = Field(
        default=None, description="Canonical source URL, if available."
    )
    source_title: Optional[str] = Field(default=None, description="Source title, if available.")

    role: Optional[str] = Field(default=None, description="Interviewed role/title if available.")
    location: Optional[str] = Field(default=None, description="Interview location if available.")
    interview_date: Optional[str] = Field(
        default=None, description="ISO date/datetime if available."
    )
    difficulty: Optional[str] = Field(default=None, description="Difficulty label if available.")
    outcome: Optional[str] = Field(default=None, description="Outcome label if available.")

    process_summary: Optional[str] = Field(
        default=None, description="Short process/experience summary."
    )
    questions: list[str] = Field(default_factory=list, description="Interview questions mentioned.")

    raw: dict[str, Any] = Field(
        default_factory=dict,
        description="Raw upstream payload (best-effort) for future enrichment/debugging.",
    )


class InterviewSyncSummary(BaseModel):
    company: str
    providers: list[InterviewProvider]
    inserted: int = 0
    updated: int = 0
    total_seen: int = 0
    warnings: list[str] = Field(default_factory=list)
