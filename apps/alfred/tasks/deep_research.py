from __future__ import annotations

import logging

from celery import shared_task

from alfred.core.dependencies import get_deep_research_service

logger = logging.getLogger(__name__)


@shared_task(name="alfred.tasks.deep_research.generate")
def deep_research_task(*, topic: str, refresh: bool = False) -> dict:
    """Generate (or fetch cached) deep research report in a background worker."""
    svc = get_deep_research_service()
    logger.info("Running deep research task (refresh=%s) for %s", refresh, topic)
    return svc.generate_report(topic, refresh=refresh)
