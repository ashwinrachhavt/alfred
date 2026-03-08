from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from alfred.core.dependencies import get_doc_storage_service
from alfred.core.settings import settings
from alfred.services.doc_storage_pg import DocStorageService
from alfred.services.hypothesis_import import import_hypothesis

router = APIRouter(prefix="/api/hypothesis", tags=["hypothesis"])
logger = logging.getLogger(__name__)


class HypothesisImportRequest(BaseModel):
    token: str | None = None
    limit: int | None = Field(default=None, ge=1, le=5000)


class ImportResponse(BaseModel):
    status: str
    result: dict[str, Any] | None = None


@router.get("/status")
def hypothesis_status() -> dict[str, Any]:
    return {"configured": bool(settings.hypothesis_token)}


@router.post("/import", response_model=ImportResponse)
def start_hypothesis_import(
    payload: HypothesisImportRequest,
    svc: DocStorageService = Depends(get_doc_storage_service),
) -> ImportResponse:
    result = import_hypothesis(
        doc_store=svc,
        token=payload.token,
        limit=payload.limit,
    )
    return ImportResponse(status="completed", result=result)
