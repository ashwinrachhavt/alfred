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
    return svc.process_document(doc_id, force=force)
