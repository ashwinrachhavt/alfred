"""Split document text into retrieval-ready chunks."""

from __future__ import annotations

import logging
from typing import Any

from alfred.pipeline.state import DocumentPipelineState

logger = logging.getLogger(__name__)


def _get_chunking_service():
    from alfred.services.chunking import ChunkingService
    return ChunkingService()


def chunk(state: DocumentPipelineState) -> dict[str, Any]:
    """Chunk cleaned_text using ChunkingService."""
    svc = _get_chunking_service()
    raw_chunks = svc.chunk(state["cleaned_text"])
    chunks = [c.model_dump() for c in raw_chunks]

    logger.info("Chunked document into %d pieces", len(chunks))

    return {
        "chunks": chunks,
        "stage": "chunk",
    }
