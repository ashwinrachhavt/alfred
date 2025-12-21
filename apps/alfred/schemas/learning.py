from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field


class TopicCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    tags: list[str] | None = None
    interview_at: datetime | None = None


class TopicUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    tags: list[str] | None = None
    status: Literal["active", "paused", "completed"] | None = None
    progress: int | None = Field(default=None, ge=0, le=100)
    interview_at: datetime | None = None


class TopicOut(BaseModel):
    id: int
    name: str
    description: str | None
    tags: list[str] | None
    status: str
    progress: int
    interview_at: datetime | None
    first_learned_at: datetime | None
    last_studied_at: datetime | None
    created_at: datetime | None
    updated_at: datetime | None


class ResourceCreate(BaseModel):
    title: str | None = Field(default=None, max_length=512)
    source_url: str | None = Field(default=None, max_length=2048)
    document_id: str | None = Field(default=None, max_length=96)
    notes: str | None = None


class ResourceOut(BaseModel):
    id: int
    topic_id: int
    title: str | None
    source_url: str | None
    document_id: str | None
    notes: str | None
    added_at: datetime
    extracted_at: datetime | None
    created_at: datetime | None
    updated_at: datetime | None


class QuizItem(BaseModel):
    question: str = Field(min_length=1)
    answer: str | None = None


class QuizGenerateRequest(BaseModel):
    resource_id: int | None = None
    question_count: int = Field(default=8, ge=1, le=25)
    source_text: str | None = Field(
        default=None,
        description="Optional raw text to generate quiz from (bypasses Mongo/document fetch).",
    )


class QuizOut(BaseModel):
    id: int
    topic_id: int
    resource_id: int | None
    items: list[QuizItem]
    created_at: datetime | None
    updated_at: datetime | None


class QuizSubmitRequest(BaseModel):
    known: list[bool] = Field(min_length=1)
    responses: list[dict] | None = None


class QuizAttemptOut(BaseModel):
    id: int
    quiz_id: int
    known: list[bool]
    responses: list[dict] | None
    score: float
    submitted_at: datetime
    created_at: datetime | None
    updated_at: datetime | None


class ReviewOut(BaseModel):
    id: int
    topic_id: int
    stage: int
    iteration: int
    due_at: datetime
    completed_at: datetime | None
    score: float | None
    attempt_id: int | None
    created_at: datetime | None
    updated_at: datetime | None


class ReviewCompleteRequest(BaseModel):
    attempt_id: int | None = None
    score: float | None = Field(default=None, ge=0.0, le=1.0)


class StudyPlanRequest(BaseModel):
    minutes_available: int = Field(ge=5, le=24 * 60)
    focus_topic_ids: list[int] | None = None
    include_new_material: bool = True


class StudyPlanItem(BaseModel):
    topic_id: int
    topic_name: str
    action: str
    minutes: int
    reason: str
    review_id: Optional[int] = None


class StudyPlanResponse(BaseModel):
    minutes_available: int
    items: list[StudyPlanItem]


class GraphNode(BaseModel):
    id: str
    label: str
    type: str
    meta: dict | None = None


class GraphEdge(BaseModel):
    source: str
    target: str
    type: str = "RELATED"
    weight: int | None = None


class GraphResponse(BaseModel):
    nodes: list[GraphNode]
    edges: list[GraphEdge]


class RetentionMetric(BaseModel):
    retention_rate_30d: float = Field(ge=0.0, le=1.0)
    sample_size: int = Field(ge=0)
    as_of: datetime
