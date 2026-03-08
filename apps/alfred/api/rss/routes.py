from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from alfred.core.dependencies import get_doc_storage_service
from alfred.core.settings import settings
from alfred.services.doc_storage_pg import DocStorageService
from alfred.services.rss_import import import_rss

router = APIRouter(prefix="/api/rss", tags=["rss"])
logger = logging.getLogger(__name__)


class RssImportRequest(BaseModel):
    feed_urls: list[str] = Field(..., min_length=1)
    limit: int | None = Field(default=None, ge=1, le=5000)


class ImportResponse(BaseModel):
    status: str
    result: dict[str, Any] | None = None


@router.get("/status")
def rss_status() -> dict[str, Any]:
    configured_feeds = getattr(settings, "rss_feed_urls", None) or []
    return {
        "configured": True,
        "configured_feed_urls": configured_feeds,
    }


@router.post("/import", response_model=ImportResponse)
def start_rss_import(
    payload: RssImportRequest,
    svc: DocStorageService = Depends(get_doc_storage_service),
) -> ImportResponse:
    try:
        result = import_rss(
            doc_store=svc,
            feed_urls=payload.feed_urls,
            limit=payload.limit,
        )
    except Exception as exc:
        logger.exception("RSS import failed")
        return ImportResponse(
            status="error",
            result={"ok": False, "error": str(exc)},
        )
    return ImportResponse(status="completed", result=result)
