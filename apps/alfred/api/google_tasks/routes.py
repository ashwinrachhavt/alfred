from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from alfred.core.dependencies import get_doc_storage_service
from alfred.core.settings import settings
from alfred.schemas.imports import ImportResponse
from alfred.services.doc_storage_pg import DocStorageService
from alfred.services.google_tasks_import import import_google_tasks

router = APIRouter(prefix="/api/google-tasks", tags=["google-tasks"])
logger = logging.getLogger(__name__)


class GoogleTasksImportRequest(BaseModel):
    user_id: str | None = None
    namespace: str | None = None
    include_completed: bool = False
    limit: int | None = Field(default=None, ge=1, le=5000)


@router.get("/status")
def google_tasks_status() -> dict[str, Any]:
    google_oauth_configured = bool(
        getattr(settings, "google_client_id", None)
        and getattr(settings, "google_client_secret", None)
    )
    tasks_scope_present = any("tasks" in s for s in getattr(settings, "google_scopes", []))
    return {
        "configured": google_oauth_configured and tasks_scope_present,
        "google_oauth_configured": google_oauth_configured,
        "tasks_scope_present": tasks_scope_present,
    }


@router.post("/import", response_model=ImportResponse)
def start_google_tasks_import(
    payload: GoogleTasksImportRequest,
    svc: DocStorageService = Depends(get_doc_storage_service),
) -> ImportResponse:
    try:
        result = import_google_tasks(
            doc_store=svc,
            user_id=payload.user_id,
            namespace=payload.namespace,
            include_completed=payload.include_completed,
            limit=payload.limit,
        )
    except Exception as exc:
        logger.exception("Google Tasks import failed")
        return ImportResponse(
            status="error",
            result={"ok": False, "error": str(exc)},
        )
    return ImportResponse(status="completed", result=result)
