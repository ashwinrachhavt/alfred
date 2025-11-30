"""Backwards-compat re-exports for Mind Palace note schemas.

Prefer importing from `alfred.schemas.mind_palace`.
"""

from .mind_palace import NoteCreateRequest, NoteResponse, NotesListResponse

__all__ = [
    "NoteCreateRequest",
    "NoteResponse",
    "NotesListResponse",
]
