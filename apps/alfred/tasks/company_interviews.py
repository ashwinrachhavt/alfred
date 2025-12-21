from __future__ import annotations

import logging

from celery import shared_task

from alfred.core.dependencies import get_company_interviews_service
from alfred.schemas.company_interviews import InterviewProvider

logger = logging.getLogger(__name__)


@shared_task(name="alfred.tasks.company_interviews.sync")
def company_interviews_sync_task(
    *,
    company: str,
    providers: list[str] | None = None,
    refresh: bool = False,
    max_items_per_provider: int = 0,
) -> dict:
    """Sync interview experiences for a company into Mongo."""
    svc = get_company_interviews_service()
    parsed: list[InterviewProvider] = []
    if providers:
        for p in providers:
            try:
                parsed.append(InterviewProvider(p))
            except Exception:
                continue
    if not parsed:
        parsed = [InterviewProvider.glassdoor, InterviewProvider.blind]

    logger.info(
        "Running company interviews sync (refresh=%s, providers=%s) for %s",
        refresh,
        [p.value for p in parsed],
        company,
    )
    res = svc.sync_company_interviews(
        company,
        providers=tuple(parsed),
        refresh=refresh,
        max_items_per_provider=max_items_per_provider,
    )
    return res.model_dump(mode="json")
