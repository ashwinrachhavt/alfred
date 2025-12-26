"""Pydantic schemas shared across the app."""

from .documents import (
    DocSummary,
    DocumentIngest,
    DocumentIngestChunk,
    NoteCreate,
    NoteCreateRequest,
    NoteResponse,
    NotesListResponse,
)
from .mind_palace_agent import AgentQueryRequest, AgentResponse, ChatMessage
from .whiteboard import (
    WhiteboardCommentCreate,
    WhiteboardCommentOut,
    WhiteboardCreate,
    WhiteboardOut,
    WhiteboardRevisionCreate,
    WhiteboardRevisionOut,
    WhiteboardUpdate,
    WhiteboardWithRevision,
)
from .writing import WritingPreset, WritingRequest, WritingResponse
from .zettel import (
    CompleteReviewRequest,
    GraphSummary,
    ZettelCardCreate,
    ZettelCardOut,
    ZettelLinkCreate,
    ZettelLinkOut,
    ZettelReviewOut,
)

__all__ = [
    # Documents
    "NoteCreate",
    "NoteCreateRequest",
    "NoteResponse",
    "NotesListResponse",
    "DocSummary",
    "DocumentIngestChunk",
    "DocumentIngest",
    # Agent
    "ChatMessage",
    "AgentQueryRequest",
    "AgentResponse",
    # Zettels
    "ZettelCardCreate",
    "ZettelCardOut",
    "ZettelLinkCreate",
    "ZettelLinkOut",
    "ZettelReviewOut",
    "CompleteReviewRequest",
    "GraphSummary",
    # Whiteboards
    "WhiteboardCreate",
    "WhiteboardUpdate",
    "WhiteboardOut",
    "WhiteboardWithRevision",
    "WhiteboardRevisionCreate",
    "WhiteboardRevisionOut",
    "WhiteboardCommentCreate",
    "WhiteboardCommentOut",
    # Writing
    "WritingPreset",
    "WritingRequest",
    "WritingResponse",
]
