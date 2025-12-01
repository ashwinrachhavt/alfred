"""Documents schemas shim.

Re-exports the Mind Palace schemas under a `documents` name to
support recent renames without breaking imports.
"""

from __future__ import annotations

from .mind_palace import (
    DocChunkRecord,
    DocSummary,
    DocumentIngest,
    DocumentIngestChunk,
    # canonical records
    DocumentRecord,
    MindPalaceDocumentRecord,
    NoteCreate,
    NoteCreateRequest,
    NoteRecord,
    NoteResponse,
    NotesListResponse,
)

__all__ = [
    "NoteCreate",
    "NoteCreateRequest",
    "NoteResponse",
    "NotesListResponse",
    "DocSummary",
    "DocumentIngestChunk",
    "DocumentIngest",
    # canonical records
    "DocumentRecord",
    "DocChunkRecord",
    "NoteRecord",
    "MindPalaceDocumentRecord",
]
