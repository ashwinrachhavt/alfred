from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional

from bson import ObjectId
from pydantic import BaseModel, ConfigDict, Field, field_validator


class JobApplicationStatus(str, Enum):
    applied = "Applied"
    interview_scheduled = "Interview Scheduled"
    offer = "Offer"
    rejected = "Rejected"
    withdrawn = "Withdrawn"


class _ObjectIdOrStr(ObjectId):
    @classmethod
    def __get_validators__(cls):  # type: ignore[override]
        yield cls.validate

    @classmethod
    def validate(cls, v: Any, _info: Any = None) -> ObjectId:  # noqa: D401
        if v is None:
            return v
        if isinstance(v, ObjectId):
            return v
        if isinstance(v, str) and ObjectId.is_valid(v):
            return ObjectId(v)
        raise TypeError("Not a valid ObjectId or str ObjectId")


class JobApplicationRecord(BaseModel):
    """Canonical Mongo record for `job_applications`."""

    model_config = ConfigDict(extra="allow", arbitrary_types_allowed=True)

    company: str
    role: str
    status: JobApplicationStatus = JobApplicationStatus.applied
    source_url: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

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
    source_url: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("company", "role")
    @classmethod
    def _non_empty_str(cls, v: str) -> str:
        if not (v or "").strip():
            raise ValueError("must be non-empty")
        return v.strip()


class JobApplicationUpdate(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    status: Optional[JobApplicationStatus] = None
    source_url: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    updated_at: Optional[datetime] = None


__all__ = [
    "JobApplicationCreate",
    "JobApplicationRecord",
    "JobApplicationStatus",
    "JobApplicationUpdate",
    "_ObjectIdOrStr",
]
