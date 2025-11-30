"""Mind Palace service package.

This package implements the Mind Palace capture and enrichment flow using
MongoDB for persistence. The API surface is intentionally small and focused
so it can be consumed from FastAPI routes or other services.

Design goals
------------
- No heavy side effects at import time (no LLM initialization).
- Keep enrichment optional; if no API key is configured, fall back to
  lightweight heuristics and mark the doc as ready.
- Reuse the existing Mongo connector/service.
"""

from __future__ import annotations

from alfred.schemas.mind_palace import (
    DocSummary,
    DocumentIngest,
    DocumentIngestChunk,
    NoteCreate,
)
from alfred.services.mind_palace.doc_storage import DocStorageService

__all__ = [
    "DocStorageService",
    "NoteCreate",
    "DocSummary",
    "DocumentIngestChunk",
    "DocumentIngest",
]
