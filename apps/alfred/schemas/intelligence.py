from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

PlanStepStatus = Literal["pending", "in_progress", "completed", "blocked", "canceled"]


class PlanStep(BaseModel):
    """A single executable step in a multi-step plan."""

    step: str = Field(..., min_length=1, max_length=240)
    status: PlanStepStatus = Field(default="pending")


class ExecutionPlan(BaseModel):
    """A compact, UI-friendly plan for incremental execution."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    goal: str = Field(..., min_length=1, max_length=600)
    steps: list[PlanStep] = Field(..., min_length=1, max_length=12)


class PlanCreateRequest(BaseModel):
    """Request to generate a plan for a goal."""

    goal: str = Field(..., min_length=1, description="What you want to accomplish.")
    context: str | None = Field(
        default=None,
        description="Optional constraints/background to help plan generation.",
    )
    max_steps: int = Field(
        default=6,
        ge=1,
        le=12,
        description="Maximum number of steps (smaller is better).",
    )


class MemoryItem(BaseModel):
    """A durable, user-relevant memory entry."""

    id: str
    text: str
    source_url: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime | None = None


class MemoryCreateRequest(BaseModel):
    """Create a memory entry."""

    text: str = Field(..., min_length=1)
    user_id: int | None = None
    source: str | None = Field(
        default=None,
        description="Where the memory came from (e.g. 'thread', 'task', 'manual').",
    )
    task_id: str | None = None
    tags: list[str] = Field(default_factory=list)
    links: list[dict[str, Any]] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class MemoryListResponse(BaseModel):
    items: list[MemoryItem]
    total: int
    skip: int
    limit: int



class LanguageDetectRequest(BaseModel):
    text: str = Field(..., min_length=1)


class LanguageDetectResponse(BaseModel):
    language: str | None = Field(default=None, description="BCP-47/ISO-ish code (e.g. 'en').")
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    provider: str = Field(default="unknown", description="Detector used (e.g. 'langid').")


class AutocompleteRequest(BaseModel):
    text: str = Field(..., min_length=1)
    tone: str | None = Field(
        default=None,
        description="Optional tone hint (e.g. 'concise', 'friendly', 'formal').",
    )
    max_chars: int = Field(default=600, ge=1, le=4000)


class AutocompleteResponse(BaseModel):
    completion: str
    language: str | None = None


class TextEditRequest(BaseModel):
    text: str = Field(..., min_length=1)
    instruction: str = Field(..., min_length=1, description="Editing instruction.")
    tone: str | None = Field(default=None)


class TextEditResponse(BaseModel):
    output: str
    language: str | None = None


class SummaryPayload(BaseModel):
    title: str | None = None
    language: str | None = None
    short: str = Field(..., min_length=1)
    bullets: list[str] = Field(default_factory=list)
    key_points: list[str] = Field(default_factory=list)


class SummarizeTextRequest(BaseModel):
    text: str = Field(..., min_length=1)
    title: str | None = None
    source_url: str | None = Field(
        default=None,
        description="Optional source URL to attach when storing.",
    )
    content_type: str = Field(
        default="text", description="text | pdf | audio | video | podcast | web"
    )
    store: bool = Field(default=True, description="Persist as a document for later Q&A.")


class SummarizeUrlRequest(BaseModel):
    url: str = Field(..., min_length=1)
    title: str | None = None
    render_js: bool = Field(
        default=False, description="Best-effort JS rendering via Firecrawl when available."
    )
    store: bool = Field(default=True)


class SummarizeResponse(BaseModel):
    summary: SummaryPayload
    doc_id: str | None = None
    content_type: str


class QaRequest(BaseModel):
    question: str = Field(..., min_length=1)
    doc_id: str | None = None
    text: str | None = None


class QaResponse(BaseModel):
    answer: str
    language: str | None = None


__all__ = [
    "ExecutionPlan",
    "PlanCreateRequest",
    "PlanStep",
    "PlanStepStatus",
    "LanguageDetectRequest",
    "LanguageDetectResponse",
    "AutocompleteRequest",
    "AutocompleteResponse",
    "TextEditRequest",
    "TextEditResponse",
    "QaRequest",
    "QaResponse",
    "SummarizeResponse",
    "SummarizeTextRequest",
    "SummarizeUrlRequest",
    "SummaryPayload",
    "MemoryCreateRequest",
    "MemoryItem",
    "MemoryListResponse",
]
