"""Index document chunks into Qdrant vector store."""

from __future__ import annotations

import logging
from typing import Any

from alfred.pipeline.state import DocumentPipelineState

logger = logging.getLogger(__name__)


def _get_knowledge_service():
    from alfred.services.knowledge import KnowledgeService
    return KnowledgeService()


def embed(state: DocumentPipelineState) -> dict[str, Any]:
    """Transform chunks to Qdrant format and index."""
    doc_id = state["doc_id"]
    chunks = state.get("chunks", [])

    if not chunks:
        logger.warning("No chunks to embed for %s", doc_id)
        return {"embedding_indexed": False, "stage": "embed"}

    svc = _get_knowledge_service()

    index_docs = [
        {
            "id": f"{doc_id}:{chunk['idx']}",
            "text": chunk["text"],
            "meta": {
                "doc_id": doc_id,
                "section": chunk.get("section"),
                "char_start": chunk.get("char_start"),
                "char_end": chunk.get("char_end"),
            },
        }
        for chunk in chunks
    ]

    ids = svc.index_documents(index_docs)
    logger.info("Indexed %d chunks for %s", len(ids), doc_id)

    return {"embedding_indexed": True, "stage": "embed"}
