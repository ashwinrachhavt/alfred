from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from alfred.core.dependencies import get_doc_storage_service
from alfred.core.settings import settings
from alfred.services.doc_storage_pg import DocStorageService
from alfred.services.google_drive_import import import_google_drive_docs

router = APIRouter(prefix="/api/gdrive", tags=["gdrive"])
logger = logging.getLogger(__name__)


class ImportRequest(BaseModel):
    user_id: str | None = None
    namespace: str | None = None
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
    """Import documents from Google Drive."""
    result = import_google_drive_docs(
        doc_store=svc,
        user_id=payload.user_id,
        namespace=payload.namespace,
        limit=payload.limit,
        since=payload.since,
    )
    return ImportResponse(status="completed", result=result)


@router.get("/status")
def gdrive_status() -> dict[str, Any]:
    """Check if Google Drive integration is configured."""
    drive_enabled = bool(settings.enable_google_drive)
    oauth_configured = bool(settings.google_client_id and settings.google_client_secret)
    return {
        "configured": drive_enabled and oauth_configured,
        "drive_enabled": drive_enabled,
        "oauth_configured": oauth_configured,
    }
