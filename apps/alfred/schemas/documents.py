"""Document and note schemas used across ingestion and retrieval."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


# -----------------
# Notes
# -----------------
class NoteCreate(BaseModel):
    text: str
    source_url: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

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
    source_url: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class NotesListResponse(BaseModel):
    items: list[NoteResponse]
    total: int
    skip: int
    limit: int


class NoteRecord(BaseModel):
    model_config = ConfigDict(extra="allow")

    text: str
    source_url: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


# -----------------
# Documents
# -----------------
CAPTURED_HOUR_MIN = 0
CAPTURED_HOUR_MAX = 23


class DocSummary(BaseModel):
    short: str | None = None
    bullets: list[str] | None = None
    key_points: list[str] | None = None


class DocumentIngestChunk(BaseModel):
    idx: int
    text: str
    tokens: int | None = None
    section: str | None = None
    char_start: int | None = None
    char_end: int | None = None
    embedding: list[float] | None = None

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
    canonical_url: str | None = None
    title: str | None = None
    content_type: str | None = None
    lang: str | None = None
    raw_markdown: str | None = None
    cleaned_text: str
    tokens: int | None = None
    hash: str | None = None
    summary: DocSummary | None = None
    topics: dict[str, Any] | None = None
    tags: list[str] | None = None
    embedding: list[float] | None = None
    captured_at: datetime | None = None
    published_at: datetime | None = None
    processed_at: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    chunks: list[DocumentIngestChunk] = Field(default_factory=list)
    session_id: str | None = None

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
    canonical_url: str | None = None
    domain: str | None = None
    title: str | None = None
    content_type: str = "web"
    lang: str | None = None
    raw_markdown: str | None = None
    cleaned_text: str
    tokens: int
    hash: str
    summary: dict[str, Any] | None = None
    topics: dict[str, Any] | None = None
    entities: dict[str, Any] | None = None
    tags: list[str] = Field(default_factory=list)
    embedding: list[float] | None = None
    captured_at: datetime
    captured_hour: int
    day_bucket: datetime
    published_at: datetime | None = None
    processed_at: datetime
    created_at: datetime
    updated_at: datetime
    session_id: str | None = None
    agent_run_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("captured_hour")
    @classmethod
    def hour_bounds(cls, v: int) -> int:
        if v < CAPTURED_HOUR_MIN or v > CAPTURED_HOUR_MAX:
            raise ValueError(
                f"captured_hour must be within {CAPTURED_HOUR_MIN}-{CAPTURED_HOUR_MAX}"
            )
        return v


class DocChunkRecord(BaseModel):
    model_config = ConfigDict(extra="allow", arbitrary_types_allowed=True)

    doc_id: str
    idx: int
    text: str
    tokens: int
    section: str | None = None
    char_start: int | None = None
    char_end: int | None = None
    embedding: list[float] | None = None
    topics: dict[str, Any] | None = None
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
    chunk_ids: list[str] = Field(default_factory=list)
    title: str | None = None
    summary: dict[str, Any] | None = None
    tags: list[str] = Field(default_factory=list)
    topics: dict[str, Any] | None = None
    annotation: str | None = None
    created_at: datetime
    updated_at: datetime
    metadata: dict[str, Any] = Field(default_factory=dict)


class DocumentDetailsResponse(BaseModel):
    """Detailed document payload used by 'Quick Look' and deep inspection views."""

    id: str
    source_url: str
    canonical_url: str | None = None
    domain: str | None = None
    title: str | None = None
    cover_image_url: str | None = Field(
        default=None, description="Optional cover image URL (generated or extracted)."
    )
    content_type: str = "web"
    lang: str | None = None
    raw_markdown: str | None = None
    cleaned_text: str
    tokens: int | None = None
    summary: dict[str, Any] | None = None
    topics: dict[str, Any] | None = None
    entities: dict[str, Any] | list[Any] | None = None
    tags: list[str] = Field(default_factory=list)
    captured_at: datetime
    day_bucket: date
    created_at: datetime
    updated_at: datetime
    session_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    enrichment: dict[str, Any] | None = None


class DocumentTextUpdateRequest(BaseModel):
    """Patch payload for editing a document's text content.

    Notes
    -----
    - `cleaned_text` is treated as the canonical plain-text version used for search.
    - `raw_markdown` can store a richer representation (e.g. TipTap Markdown).
    - `tiptap_json` is optionally persisted into the document `metadata` for future rich editing.
    """

    raw_markdown: str | None = None
    cleaned_text: str | None = None
    tiptap_json: dict[str, Any] | None = None

    @model_validator(mode="after")
    def _must_include_a_field(self) -> DocumentTextUpdateRequest:
        if self.raw_markdown is None and self.cleaned_text is None and self.tiptap_json is None:
            raise ValueError("At least one of raw_markdown, cleaned_text, tiptap_json must be set")
        return self


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
    pipeline_status: str = Field(
        default="complete",
        description="Processing status: pending, processing, complete, error.",
    )


class ExplorerDocumentsResponse(BaseModel):
    """Cursor-paginated documents list for explorer views (Atheneum)."""

    items: list[ExplorerDocumentItem]
    next_cursor: str | None = Field(
        default=None,
        description="Opaque cursor for the next page; omit/None when there is no next page.",
    )
    total_count: int = Field(
        default=0,
        description="Total number of matching documents (ignoring cursor position).",
    )
    limit: int
    filter_topic: str | None = None
    search: str | None = None


class SemanticMapPoint(BaseModel):
    """A single point (document) in the semantic map."""

    id: str
    pos: list[float] = Field(..., min_length=3, max_length=3, description="XYZ position.")
    color: str = Field(..., description="Hex color derived from primary topic.")
    label: str = Field(..., description="Display label (best-effort title).")
    primary_topic: str | None = None


class SemanticMapResponse(BaseModel):
    """3D semantic map payload for the Galaxy view."""

    points: list[SemanticMapPoint]


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
