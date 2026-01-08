"""Document and note schemas used across ingestion and retrieval."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


# -----------------
# Notes
# -----------------
class NoteCreate(BaseModel):
    text: str
    source_url: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("text")
    @classmethod
    def text_must_have_content(cls, value: str) -> str:
        trimmed = (value or "").strip()
        if not trimmed:
            raise ValueError("text must not be empty")
        return trimmed


NoteCreateRequest = NoteCreate


class NoteResponse(BaseModel):
    id: str
    text: str
    source_url: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class NotesListResponse(BaseModel):
    items: List[NoteResponse]
    total: int
    skip: int
    limit: int


class NoteRecord(BaseModel):
    model_config = ConfigDict(extra="allow")

    text: str
    source_url: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


# -----------------
# Documents
# -----------------
class DocSummary(BaseModel):
    short: Optional[str] = None
    bullets: Optional[List[str]] = None
    key_points: Optional[List[str]] = None


class DocumentIngestChunk(BaseModel):
    idx: int
    text: str
    tokens: Optional[int] = None
    section: Optional[str] = None
    char_start: Optional[int] = None
    char_end: Optional[int] = None
    embedding: Optional[List[float]] = None

    @field_validator("idx")
    @classmethod
    def idx_nonneg(cls, v: int) -> int:
        if v < 0:
            raise ValueError("idx must be >= 0")
        return v

    @field_validator("text")
    @classmethod
    def chunk_text_not_empty(cls, v: str) -> str:
        if not (v or "").strip():
            raise ValueError("chunk text must not be empty")
        return v


class DocumentIngest(BaseModel):
    source_url: str
    canonical_url: Optional[str] = None
    title: Optional[str] = None
    content_type: Optional[str] = None
    lang: Optional[str] = None
    raw_markdown: Optional[str] = None
    cleaned_text: str
    tokens: Optional[int] = None
    hash: Optional[str] = None
    summary: Optional[DocSummary] = None
    topics: Optional[Dict[str, Any]] = None
    tags: Optional[List[str]] = None
    embedding: Optional[List[float]] = None
    captured_at: Optional[datetime] = None
    published_at: Optional[datetime] = None
    processed_at: Optional[datetime] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    chunks: List[DocumentIngestChunk] = Field(default_factory=list)
    session_id: Optional[str] = None

    @field_validator("cleaned_text")
    @classmethod
    def cleaned_text_not_empty(cls, v: str) -> str:
        if not (v or "").strip():
            raise ValueError("cleaned_text must not be empty")
        return v.strip()

    @field_validator("source_url")
    @classmethod
    def source_url_required(cls, v: str) -> str:
        if not (v or "").strip():
            raise ValueError("source_url required")
        return v


class DocumentRecord(BaseModel):
    model_config = ConfigDict(extra="allow", arbitrary_types_allowed=True)

    source_url: str
    canonical_url: Optional[str] = None
    domain: Optional[str] = None
    title: Optional[str] = None
    content_type: str = "web"
    lang: Optional[str] = None
    raw_markdown: Optional[str] = None
    cleaned_text: str
    tokens: int
    hash: str
    summary: Optional[Dict[str, Any]] = None
    topics: Optional[Dict[str, Any]] = None
    entities: Optional[Dict[str, Any]] = None
    tags: List[str] = Field(default_factory=list)
    embedding: Optional[List[float]] = None
    captured_at: datetime
    captured_hour: int
    day_bucket: datetime
    published_at: Optional[datetime] = None
    processed_at: datetime
    created_at: datetime
    updated_at: datetime
    session_id: Optional[str] = None
    agent_run_id: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("captured_hour")
    @classmethod
    def hour_bounds(cls, v: int) -> int:
        if v < 0 or v > 23:
            raise ValueError("captured_hour must be within 0-23")
        return v


class DocChunkRecord(BaseModel):
    model_config = ConfigDict(extra="allow", arbitrary_types_allowed=True)

    doc_id: str
    idx: int
    text: str
    tokens: int
    section: Optional[str] = None
    char_start: Optional[int] = None
    char_end: Optional[int] = None
    embedding: Optional[List[float]] = None
    topics: Optional[Dict[str, Any]] = None
    captured_at: datetime
    captured_hour: int
    day_bucket: datetime
    created_at: datetime

    @field_validator("idx")
    @classmethod
    def idx_nonneg(cls, v: int) -> int:
        if v < 0:
            raise ValueError("idx must be >= 0")
        return v


class MindPalaceDocumentRecord(BaseModel):
    model_config = ConfigDict(extra="allow", arbitrary_types_allowed=True)

    doc_id: str
    chunk_ids: List[str] = Field(default_factory=list)
    title: Optional[str] = None
    summary: Optional[Dict[str, Any]] = None
    tags: List[str] = Field(default_factory=list)
    topics: Optional[Dict[str, Any]] = None
    annotation: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    metadata: Dict[str, Any] = Field(default_factory=dict)


class DocumentDetailsResponse(BaseModel):
    """Detailed document payload used by 'Quick Look' and deep inspection views."""

    id: str
    source_url: str
    canonical_url: Optional[str] = None
    domain: Optional[str] = None
    title: Optional[str] = None
    cover_image_url: str | None = Field(
        default=None, description="Optional cover image URL (generated or extracted)."
    )
    content_type: str = "web"
    lang: Optional[str] = None
    raw_markdown: Optional[str] = None
    cleaned_text: str
    tokens: Optional[int] = None
    summary: Optional[Dict[str, Any]] = None
    topics: Optional[Dict[str, Any]] = None
    entities: Optional[Dict[str, Any]] = None
    tags: List[str] = Field(default_factory=list)
    captured_at: datetime
    day_bucket: date
    created_at: datetime
    updated_at: datetime
    session_id: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    enrichment: Optional[Dict[str, Any]] = None


class ExplorerDocumentItem(BaseModel):
    """A lightweight document summary for explorer views (Shelf/Stream)."""

    id: str
    title: str = Field(..., description="Display title (best-effort).")
    cover_image_url: str | None = Field(
        default=None, description="Optional cover/thumbnail URL (if available)."
    )
    summary: str | None = Field(default=None, description="Short summary (optional).")
    created_at: datetime
    day_bucket: date
    primary_topic: str | None = None
    source_url: str | None = None
    canonical_url: str | None = None


class ExplorerDocumentsResponse(BaseModel):
    """Cursor-paginated documents list for explorer views (Atheneum)."""

    items: List[ExplorerDocumentItem]
    next_cursor: str | None = Field(
        default=None,
        description="Opaque cursor for the next page; omit/None when there is no next page.",
    )
    limit: int
    filter_topic: str | None = None
    search: str | None = None


class SemanticMapPoint(BaseModel):
    """A single point (document) in the semantic map."""

    id: str
    pos: List[float] = Field(..., min_length=3, max_length=3, description="XYZ position.")
    color: str = Field(..., description="Hex color derived from primary topic.")
    label: str = Field(..., description="Display label (best-effort title).")
    primary_topic: str | None = None


class SemanticMapResponse(BaseModel):
    """3D semantic map payload for the Galaxy view."""

    points: List[SemanticMapPoint]


__all__ = [
    "DocChunkRecord",
    "DocSummary",
    "DocumentIngest",
    "DocumentIngestChunk",
    "DocumentDetailsResponse",
    "DocumentRecord",
    "ExplorerDocumentItem",
    "ExplorerDocumentsResponse",
    "MindPalaceDocumentRecord",
    "NoteCreate",
    "NoteCreateRequest",
    "NoteRecord",
    "NoteResponse",
    "NotesListResponse",
    "SemanticMapPoint",
    "SemanticMapResponse",
]
