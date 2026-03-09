from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from alfred.core.dependencies import get_doc_storage_service
from alfred.schemas.imports import ImportResponse
from alfred.services.doc_storage_pg import DocStorageService
from alfred.services.semantic_scholar_import import import_semantic_scholar

router = APIRouter(prefix="/api/semantic-scholar", tags=["semantic-scholar"])
logger = logging.getLogger(__name__)


class SemanticScholarImportRequest(BaseModel):
    query: str
    api_key: str | None = None
    limit: int | None = Field(default=None, ge=1, le=5000)
    year: str | None = None


@router.get("/status")
def semantic_scholar_status() -> dict[str, Any]:
    return {"configured": True}


@router.post("/import", response_model=ImportResponse)
def start_semantic_scholar_import(
    payload: SemanticScholarImportRequest,
    svc: DocStorageService = Depends(get_doc_storage_service),
) -> ImportResponse:
    try:
        result = import_semantic_scholar(
            doc_store=svc,
            query=payload.query,
            api_key=payload.api_key,
            limit=payload.limit,
            year=payload.year,
        )
    except Exception as exc:
        logger.exception("Semantic Scholar import failed")
        return ImportResponse(
            status="error",
            result={"ok": False, "error": str(exc)},
        )
    return ImportResponse(status="completed", result=result)
