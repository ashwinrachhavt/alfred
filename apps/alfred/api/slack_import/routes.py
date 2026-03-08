from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from alfred.core.dependencies import get_doc_storage_service
from alfred.core.settings import settings
from alfred.services.doc_storage_pg import DocStorageService
from alfred.services.slack_import import import_slack

router = APIRouter(prefix="/api/slack", tags=["slack"])
logger = logging.getLogger(__name__)


class ImportRequest(BaseModel):
    token: str | None = None
    channel_ids: list[str] = Field(default_factory=list)
    limit: int | None = Field(default=None, ge=1, le=10_000)
    since: str | None = None
    run_inline: bool = False


class ImportResponse(BaseModel):
    status: str
    result: dict[str, Any] | None = None


@router.post("/import", response_model=ImportResponse)
def start_import(
    payload: ImportRequest,
    svc: DocStorageService = Depends(get_doc_storage_service),
) -> ImportResponse:
    """Import messages from Slack channels."""
    result = import_slack(
        doc_store=svc,
        token=payload.token,
        channel_ids=payload.channel_ids,
        limit=payload.limit,
        since=payload.since,
    )
    return ImportResponse(status="completed", result=result)


@router.get("/status")
def slack_status() -> dict[str, Any]:
    """Check if Slack integration is configured."""
    configured = bool(
        settings.slack_api_key is not None
        and settings.slack_api_key.get_secret_value().strip()
    )
    return {"configured": configured}
