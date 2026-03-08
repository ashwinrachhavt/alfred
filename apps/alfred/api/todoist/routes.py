from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from alfred.core.dependencies import get_doc_storage_service
from alfred.core.settings import settings
from alfred.services.doc_storage_pg import DocStorageService
from alfred.services.todoist_import import import_todoist

router = APIRouter(prefix="/api/todoist", tags=["todoist"])
logger = logging.getLogger(__name__)


class TodoistImportRequest(BaseModel):
    token: str | None = None
    project_id: str | None = None
    include_completed: bool = False
    limit: int | None = Field(default=None, ge=1, le=5000)


class ImportResponse(BaseModel):
    status: str
    result: dict[str, Any] | None = None


@router.get("/status")
def todoist_status() -> dict[str, Any]:
    return {"configured": bool(settings.todoist_token)}


@router.post("/import", response_model=ImportResponse)
def start_todoist_import(
    payload: TodoistImportRequest,
    svc: DocStorageService = Depends(get_doc_storage_service),
) -> ImportResponse:
    result = import_todoist(
        doc_store=svc,
        token=payload.token,
        project_id=payload.project_id,
        include_completed=payload.include_completed,
        limit=payload.limit,
    )
    return ImportResponse(status="completed", result=result)
