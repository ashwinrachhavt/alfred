"""Load a document from PostgreSQL into pipeline state."""

from __future__ import annotations

import hashlib
import logging
import time
from typing import Any

from alfred.pipeline.state import DocumentPipelineState

logger = logging.getLogger(__name__)


def _get_doc_storage():
    from alfred.core.dependencies import get_doc_storage_service
    return get_doc_storage_service()


def load_document(state: DocumentPipelineState) -> dict[str, Any]:
    """Fetch DocumentRow and populate content fields in state.

    Retries once with 2s backoff if doc not found (ingestion race condition).
    """
    doc_id = state["doc_id"]
    svc = _get_doc_storage()

    doc = svc.get_document_details(doc_id)
    if doc is None:
        logger.warning("Document %s not found, retrying in 2s...", doc_id)
        time.sleep(2)
        doc = svc.get_document_details(doc_id)
    if doc is None:
        raise ValueError(f"Document {doc_id} not found after retry")

    cleaned_text = doc.get("cleaned_text") or ""
    content_hash = hashlib.sha256(cleaned_text.encode()).hexdigest()

    logger.info("Loaded document %s: %s", doc_id, doc.get("title", "untitled"))

    return {
        "title": doc.get("title") or "untitled",
        "cleaned_text": cleaned_text,
        "raw_markdown": doc.get("raw_markdown") or "",
        "content_hash": content_hash,
        "stage": "load_document",
    }
