from __future__ import annotations

import logging

from celery import shared_task

from alfred.core.dependencies import get_doc_storage_service

logger = logging.getLogger(__name__)


@shared_task(name="alfred.tasks.document_enrichment.enrich")
def document_enrichment_task(*, doc_id: str, force: bool = False) -> dict:
    """Enrich an existing stored document (LLM + optional graph)."""
    svc = get_doc_storage_service()
    logger.info("Running document enrichment task (force=%s) for %s", force, doc_id)
    return svc.enrich_document(doc_id, force=force)
