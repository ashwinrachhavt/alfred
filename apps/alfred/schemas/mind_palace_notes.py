"""Backwards-compat re-exports for Mind Palace note schemas.

Prefer importing from `alfred.schemas.documents`.
"""

from .documents import NoteCreateRequest, NoteResponse, NotesListResponse

__all__ = [
    "NoteCreateRequest",
    "NoteResponse",
    "NotesListResponse",
]
