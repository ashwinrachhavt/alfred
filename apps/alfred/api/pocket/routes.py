from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from alfred.core.dependencies import get_doc_storage_service
from alfred.core.settings import settings
from alfred.schemas.imports import ImportResponse
from alfred.services.doc_storage_pg import DocStorageService
from alfred.services.pocket_import import import_pocket

router = APIRouter(prefix="/api/pocket", tags=["pocket"])
logger = logging.getLogger(__name__)


class PocketImportRequest(BaseModel):
    consumer_key: str | None = None
    access_token: str | None = None
    limit: int | None = Field(default=None, ge=1, le=5000)
    since: str | None = None
    tag: str | None = None


@router.get("/status")
def pocket_status() -> dict[str, Any]:
    return {
        "configured": bool(settings.pocket_consumer_key and settings.pocket_access_token),
    }


@router.post("/import", response_model=ImportResponse)
def start_pocket_import(
    payload: PocketImportRequest,
    svc: DocStorageService = Depends(get_doc_storage_service),
) -> ImportResponse:
    try:
        result = import_pocket(
            doc_store=svc,
            consumer_key=payload.consumer_key,
            access_token=payload.access_token,
            limit=payload.limit,
            since=payload.since,
            tag=payload.tag,
        )
    except Exception as exc:
        logger.exception("Pocket import failed")
        return ImportResponse(
            status="error",
            result={"ok": False, "error": str(exc)},
        )
    return ImportResponse(status="completed", result=result)
