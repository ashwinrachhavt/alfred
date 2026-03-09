from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from alfred.core.dependencies import get_doc_storage_service
from alfred.schemas.imports import ImportResponse
from alfred.services.arxiv_import import import_arxiv
from alfred.services.doc_storage_pg import DocStorageService

router = APIRouter(prefix="/api/arxiv", tags=["arxiv"])
logger = logging.getLogger(__name__)


class ImportRequest(BaseModel):
    query: str = ""
    categories: list[str] = Field(default_factory=list)
    date_from: str | None = None
    date_to: str | None = None
    max_results: int = Field(default=50, ge=1, le=5_000)
    run_inline: bool = False


@router.post("/import", response_model=ImportResponse)
def start_import(
    payload: ImportRequest,
    svc: DocStorageService = Depends(get_doc_storage_service),
) -> ImportResponse:
    """Import papers from arXiv."""
    try:
        result = import_arxiv(
            doc_store=svc,
            query=payload.query,
            categories=payload.categories,
            date_from=payload.date_from,
            date_to=payload.date_to,
            max_results=payload.max_results,
        )
    except Exception as exc:
        logger.exception("ArXiv import failed")
        return ImportResponse(
            status="error",
            result={"ok": False, "error": str(exc)},
        )
    return ImportResponse(status="completed", result=result)


@router.get("/status")
def arxiv_status() -> dict[str, Any]:
    """Check if arXiv integration is configured. No auth required."""
    return {"configured": True}
