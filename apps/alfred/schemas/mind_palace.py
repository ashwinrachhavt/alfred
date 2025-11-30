from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator


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


# Alias used at the API boundary to avoid duplicate definitions
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
    # raw_html removed intentionally; we do not store HTML
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


__all__ = [
    # Notes
    "NoteCreate",
    "NoteCreateRequest",
    "NoteResponse",
    "NotesListResponse",
    # Documents
    "DocSummary",
    "DocumentIngestChunk",
    "DocumentIngest",
]
