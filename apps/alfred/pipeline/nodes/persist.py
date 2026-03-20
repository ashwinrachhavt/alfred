"""Write pipeline results back to the DocumentRow in PostgreSQL."""

from __future__ import annotations

import logging
from typing import Any

from alfred.pipeline.state import DocumentPipelineState

logger = logging.getLogger(__name__)


def _get_doc_storage():
    from alfred.core.dependencies import get_doc_storage_service
    return get_doc_storage_service()


def persist(state: DocumentPipelineState) -> dict[str, Any]:
    """Write enrichment, classification, and chunks back to DocumentRow."""
    doc_id = state["doc_id"]
    svc = _get_doc_storage()

    enrichment = state.get("enrichment", {})
    classification = state.get("classification", {})

    update_data = {
        "enrichment": enrichment,
        "summary": enrichment.get("summary"),
        "topics": enrichment.get("topics") or classification.get("topic"),
        "tags": enrichment.get("tags", []),
        "entities": enrichment.get("entities"),
        "embedding": enrichment.get("embedding"),
        "concepts": {
            "entities": enrichment.get("entities", []),
            "relations": enrichment.get("relations", []),
            "topics": classification.get("microtopics", []),
            "domain": classification.get("domain"),
            "subdomain": classification.get("subdomain"),
        },
    }

    svc.update_document_enrichment(doc_id, update_data)
    logger.info("Persisted pipeline results for %s", doc_id)

    return {"stage": "persist"}
