from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class JobApplicationStatus(str, Enum):
    applied = "Applied"
    interview_scheduled = "Interview Scheduled"
    offer = "Offer"
    rejected = "Rejected"
    withdrawn = "Withdrawn"


class JobApplicationRecord(BaseModel):
    """Canonical Mongo record for `job_applications`."""

    model_config = ConfigDict(extra="allow", arbitrary_types_allowed=True)

    company: str
    role: str
    status: JobApplicationStatus = JobApplicationStatus.applied
    source_url: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime | None = None
    updated_at: datetime | None = None

    @field_validator("company", "role")
    @classmethod
    def _non_empty_str(cls, v: str) -> str:
        if not (v or "").strip():
            raise ValueError("must be non-empty")
        return v.strip()


class JobApplicationCreate(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    company: str
    role: str
    source_url: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("company", "role")
    @classmethod
    def _non_empty_str(cls, v: str) -> str:
        if not (v or "").strip():
            raise ValueError("must be non-empty")
        return v.strip()


class JobApplicationUpdate(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    status: JobApplicationStatus | None = None
    source_url: str | None = None
    metadata: dict[str, Any] | None = None
    updated_at: datetime | None = None

__all__ = [
    "JobApplicationCreate",
    "JobApplicationRecord",
    "JobApplicationStatus",
    "JobApplicationUpdate",
]
