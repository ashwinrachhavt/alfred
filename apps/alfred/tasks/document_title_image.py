from __future__ import annotations

import logging

from celery import shared_task

from alfred.core.dependencies import get_doc_storage_service

logger = logging.getLogger(__name__)


@shared_task(name="alfred.tasks.document_title_image.generate")
def document_title_image_task(
    *,
    doc_id: str,
    force: bool = False,
    model: str = "gpt-image-1",
    size: str = "1024x1024",
    quality: str = "high",
) -> dict:
    """Generate and store a cover image for a document."""

    svc = get_doc_storage_service()
    logger.info("Generating document title image (force=%s) for %s", force, doc_id)
    return svc.generate_document_title_image(
        doc_id,
        force=force,
        model=model,
        size=size,
        quality=quality,
    )

