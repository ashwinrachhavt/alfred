from __future__ import annotations

import logging

from celery import shared_task

from alfred.core.dependencies import get_doc_storage_service

logger = logging.getLogger(__name__)


@shared_task(name="alfred.tasks.document_processing.process")
def document_processing_task(*, doc_id: str, force: bool = False) -> dict:
    """Process a stored document (chunking + optional enrichment/classification)."""
    svc = get_doc_storage_service()
    logger.info("Running document processing task (force=%s) for %s", force, doc_id)
    result = svc.process_document(doc_id, force=force)

    # Mark document as fully processed
    try:
        from alfred.tasks.document_pipeline import _set_pipeline_status

        _set_pipeline_status(doc_id, "complete")
    except Exception:
        logger.warning("Failed to set pipeline_status=complete for %s", doc_id, exc_info=True)

    return result
