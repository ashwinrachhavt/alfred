from __future__ import annotations

import logging

from celery import shared_task

from alfred.core.dependencies import get_company_research_service

logger = logging.getLogger(__name__)


@shared_task(name="alfred.tasks.company_research.generate")
def company_research_task(*, company: str, refresh: bool = False) -> dict:
    """Generate (or fetch cached) company research in a background worker."""
    svc = get_company_research_service()
    logger.info("Running company research task (refresh=%s) for %s", refresh, company)
    return svc.generate_report(company, refresh=refresh)
