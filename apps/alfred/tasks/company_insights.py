from __future__ import annotations

import logging

from celery import shared_task

from alfred.core.dependencies import get_company_insights_service

logger = logging.getLogger(__name__)


@shared_task(name="alfred.tasks.company_insights.generate")
def company_insights_task(*, company: str, role: str | None = None, refresh: bool = False) -> dict:
    """Generate (or fetch cached) company culture insights in a background worker."""
    svc = get_company_insights_service()
    logger.info("Running company insights task (refresh=%s) for %s", refresh, company)
    return svc.generate_report(company, role=role, refresh=refresh)
