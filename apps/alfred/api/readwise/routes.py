from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from alfred.core.dependencies import get_doc_storage_service
from alfred.core.settings import settings
from alfred.services.doc_storage_pg import DocStorageService
from alfred.services.readwise_import import import_readwise

router = APIRouter(prefix="/api/readwise", tags=["readwise"])
logger = logging.getLogger(__name__)


class ImportRequest(BaseModel):
    token: str | None = None
    since: str | None = None
    limit: int | None = Field(default=None, ge=1, le=10_000)
    category: str | None = None
    run_inline: bool = False


class ImportResponse(BaseModel):
    status: str
    result: dict[str, Any] | None = None


@router.post("/import", response_model=ImportResponse)
def start_import(
    payload: ImportRequest,
    svc: DocStorageService = Depends(get_doc_storage_service),
) -> ImportResponse:
    """Import highlights and books from Readwise."""
    result = import_readwise(
        doc_store=svc,
        token=payload.token,
        since=payload.since,
        limit=payload.limit,
        category=payload.category,
    )
    return ImportResponse(status="completed", result=result)


@router.get("/status")
def readwise_status() -> dict[str, Any]:
    """Check if Readwise integration is configured."""
    configured = bool(
        settings.readwise_token is not None
        and settings.readwise_token.get_secret_value().strip()
    )
    return {"configured": configured}
