"""Schemas for Alfred Notes (hierarchical markdown-first pages)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class NoteCreateRequest(BaseModel):
    title: str | None = Field(default=None, description="Note title (defaults to 'Untitled').")
    icon: str | None = Field(default=None, description="Optional emoji icon.")
    cover_image: str | None = Field(default=None, description="Optional cover image URL.")
    parent_id: str | None = Field(default=None, description="Parent note id (None for root).")
    workspace_id: str | None = Field(default=None, description="Workspace id (defaults to user).")
    content_markdown: str | None = Field(default=None, description="Markdown content.")
    content_json: dict[str, Any] | None = Field(
        default=None, description="Optional editor JSON (e.g., TipTap)."
    )


class NoteUpdateRequest(BaseModel):
    title: str | None = None
    icon: str | None = None
    cover_image: str | None = None
    content_markdown: str | None = None
    content_json: dict[str, Any] | None = None
    is_archived: bool | None = None


class NoteMoveRequest(BaseModel):
    parent_id: str | None = Field(default=None, description="New parent note id (None for root).")
    position: int | None = Field(
        default=None,
        description="New 0-based position within the parent (defaults to end).",
        ge=0,
    )


class NoteSummary(BaseModel):
    id: str
    title: str
    icon: str | None = None
    cover_image: str | None = None
    parent_id: str | None = None
    workspace_id: str
    position: int
    is_archived: bool
    created_at: datetime
    updated_at: datetime


class NoteResponse(NoteSummary):
    content_markdown: str
    content_json: dict[str, Any] | None = None
    created_by: int | None = None
    last_edited_by: int | None = None


class NoteAssetResponse(BaseModel):
    id: str
    note_id: str
    workspace_id: str
    file_name: str
    mime_type: str
    size_bytes: int
    sha256: str | None = None
    url: str
    created_at: datetime
    created_by: int | None = None


class NotesListResponse(BaseModel):
    items: list[NoteSummary]
    total: int
    skip: int
    limit: int


class NoteTreeNode(BaseModel):
    note: NoteSummary
    children: list[NoteTreeNode] = Field(default_factory=list)


class NoteTreeResponse(BaseModel):
    workspace_id: str
    items: list[NoteTreeNode]


class NoteFilesystemEntryResponse(BaseModel):
    name: str
    path: str
    kind: str
    hidden: bool
    importable: bool
    size_bytes: int | None = None
    reason: str | None = None


class NoteFilesystemBrowseResponse(BaseModel):
    path: str
    name: str
    parent_path: str | None = None
    root_path: str
    items: list[NoteFilesystemEntryResponse]


class NoteFilesystemImportRequest(BaseModel):
    workspace_id: str
    path: str
    parent_id: str | None = None
    max_files: int = Field(default=200, ge=1, le=500)


class NoteFilesystemImportResponse(BaseModel):
    source_path: str
    root_note_id: str
    imported_count: int
    skipped_count: int
    skipped_paths: list[str]


__all__ = [
    "NoteCreateRequest",
    "NoteAssetResponse",
    "NoteFilesystemBrowseResponse",
    "NoteFilesystemEntryResponse",
    "NoteFilesystemImportRequest",
    "NoteFilesystemImportResponse",
    "NoteMoveRequest",
    "NoteResponse",
    "NotesListResponse",
    "NoteSummary",
    "NoteTreeNode",
    "NoteTreeResponse",
    "NoteUpdateRequest",
]
