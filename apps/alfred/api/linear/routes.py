from __future__ import annotations

import logging
from typing import Any, Literal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from alfred.core.dependencies import get_doc_storage_service
from alfred.core.settings import settings
from alfred.services.doc_storage_pg import DocStorageService
from alfred.services.linear import LinearService, get_linear_service
from alfred.services.linear_import import import_linear

router = APIRouter(prefix="/api/linear", tags=["linear"])
logger = logging.getLogger(__name__)


class LinearImportRequest(BaseModel):
    token: str | None = None
    limit: int | None = Field(default=None, ge=1, le=5000)
    since: str | None = None


class LinearImportResponse(BaseModel):
    status: str
    result: dict[str, Any] | None = None


@router.get("/status")
def linear_status(
    validate: bool = Query(False, description="When true, perform a lightweight API call"),
) -> dict[str, Any]:
    configured = bool(settings.linear_api_key)
    if not validate:
        return {"configured": configured}

    svc = get_linear_service()
    viewer = svc.viewer()
    return {"configured": configured, "viewer": viewer}


@router.get("/issues")
def list_issues(
    start_date: str | None = Query(
        None,
        description="YYYY-MM-DD; if provided with end_date, filters issues created/updated in range",
    ),
    end_date: str | None = Query(None, description="YYYY-MM-DD"),
    include_comments: bool = Query(False),
    limit: int = Query(100, ge=1, le=500),
    format: Literal["raw", "formatted", "markdown"] = Query("raw"),
    svc: LinearService = Depends(get_linear_service),
) -> dict[str, Any]:
    if (start_date and not end_date) or (end_date and not start_date):
        return {
            "count": 0,
            "items": [],
            "error": "Provide both start_date and end_date (YYYY-MM-DD)",
        }

    if start_date and end_date:
        issues = svc.list_issues_by_date_range(
            start_date=start_date,
            end_date=end_date,
            include_comments=include_comments,
            limit=limit,
        )
    else:
        issues = svc.list_issues(include_comments=include_comments, limit=limit)

    if format == "raw":
        items: list[Any] = issues
    elif format == "formatted":
        items = [svc.format_issue(issue) for issue in issues]
    else:
        items = [svc.issue_to_markdown(issue) for issue in issues]

    return {"count": len(items), "items": items}


@router.post("/import", response_model=LinearImportResponse)
def start_linear_import(
    payload: LinearImportRequest,
    svc: DocStorageService = Depends(get_doc_storage_service),
) -> LinearImportResponse:
    try:
        result = import_linear(
            doc_store=svc,
            token=payload.token,
            limit=payload.limit,
            since=payload.since,
        )
    except Exception as exc:
        logger.exception("Linear import failed")
        return LinearImportResponse(
            status="error",
            result={"ok": False, "error": str(exc)},
        )
    return LinearImportResponse(status="completed", result=result)
