from __future__ import annotations

import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(name="alfred.tasks.taxonomy_reclassify.reclassify_all")
def reclassify_all_task() -> dict[str, int]:
    """Batch reclassify all documents using the taxonomy classifier (async via Celery)."""
    from alfred.core.dependencies import get_extraction_service
    from alfred.services.taxonomy_service import TaxonomyService

    svc = TaxonomyService(extraction_service=get_extraction_service())
    logger.info("Starting async batch reclassification")
    stats = svc.reclassify_all()
    logger.info("Batch reclassification complete: %s", stats)
    return stats
