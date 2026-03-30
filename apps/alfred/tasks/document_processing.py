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


@shared_task(name="alfred.tasks.document_processing.fetch_organize")
def fetch_organize_task(*, doc_id: str, source_url: str, force: bool = False) -> dict:
    """Fetch full page content via Firecrawl, update document, trigger enrichment."""
    from alfred.connectors.firecrawl_connector import FirecrawlClient
    from alfred.core.celery_client import get_celery_client

    logger.info("Fetching and organizing document %s from %s (force=%s)", doc_id, source_url, force)
    svc = get_doc_storage_service()
    fc = FirecrawlClient()
    result = fc.scrape(source_url)

    if not result.success or not result.markdown:
        return {"status": "error", "error": f"Failed to fetch: {result.error}"}

    markdown = result.markdown.strip()
    min_fetch_length = 50
    if len(markdown) < min_fetch_length:
        return {"status": "error", "error": "Fetched content too short"}

    # Update the document with the full markdown content
    svc.update_document_text(
        doc_id,
        raw_markdown=markdown,
        cleaned_text=markdown,
    )

    # Trigger enrichment
    try:
        celery_client = get_celery_client()
        celery_client.send_task(
            "alfred.tasks.document_enrichment.enrich",
            kwargs={"doc_id": doc_id, "force": True},
        )
    except Exception:
        logger.warning("Failed to enqueue enrichment for %s", doc_id, exc_info=True)

    return {"status": "fetched_and_enriching", "tokens": len(markdown.split())}
