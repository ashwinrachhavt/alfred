from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class ZettelCardCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    content: str | None = None
    summary: str | None = None
    tags: list[str] | None = None
    topic: str | None = Field(default=None, max_length=128)
    source_url: str | None = Field(default=None, max_length=2048)
    document_id: str | None = None
    importance: int = Field(default=0, ge=0, le=10)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    status: str = Field(default="active")


class ZettelCardOut(BaseModel):
    id: int
    title: str
    content: str | None = None
    summary: str | None = None
    tags: list[str] | None = None
    topic: str | None = None
    source_url: str | None = None
    document_id: str | None = None
    importance: int
    confidence: float
    status: str
    created_at: datetime | None = None
    updated_at: datetime | None = None

    class Config:
        from_attributes = True


class ZettelLinkCreate(BaseModel):
    to_card_id: int
    type: str = Field(default="reference", max_length=64)
    context: str | None = None
    bidirectional: bool = True


class ZettelLinkOut(BaseModel):
    id: int
    from_card_id: int
    to_card_id: int
    type: str
    context: str | None = None
    bidirectional: bool
    created_at: datetime | None = None
    updated_at: datetime | None = None

    class Config:
        from_attributes = True


class ZettelReviewOut(BaseModel):
    id: int
    card_id: int
    stage: int
    iteration: int
    due_at: datetime
    completed_at: datetime | None = None
    score: float | None = None

    class Config:
        from_attributes = True


class CompleteReviewRequest(BaseModel):
    score: float | None = Field(default=None, ge=0.0, le=1.0)


class GraphSummary(BaseModel):
    nodes: list[dict]
    edges: list[dict]


class LinkQuality(BaseModel):
    semantic_score: float
    tag_overlap: float
    topic_match: bool
    citation_overlap: int
    temporal_proximity_days: float | None = None
    composite_score: float
    confidence: str


class LinkSuggestion(BaseModel):
    to_card_id: int
    to_title: str
    to_topic: str | None = None
    to_tags: list[str] | None = None
    reason: str
    scores: LinkQuality
