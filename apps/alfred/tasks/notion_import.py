from __future__ import annotations

import logging

from celery import shared_task

from alfred.core.dependencies import get_doc_storage_service
from alfred.services.notion_import import import_notion_workspace

logger = logging.getLogger(__name__)


@shared_task(name="alfred.tasks.notion_import.import_workspace")
def notion_import_workspace_task(
    *,
    workspace_id: str | None = None,
    limit: int | None = None,
    since: str | None = None,
    include_archived: bool = False,
    sleep_s: float = 0.35,
) -> dict:
    """Import Notion pages into Alfred documents."""

    svc = get_doc_storage_service()
    logger.info(
        "Starting Notion workspace import (workspace_id=%s, limit=%s, since=%s)",
        workspace_id,
        limit,
        since,
    )
    return import_notion_workspace(
        doc_store=svc,
        workspace_id=workspace_id,
        limit=limit,
        since=since,
        include_archived=include_archived,
        sleep_s=sleep_s,
    )
