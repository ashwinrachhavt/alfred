from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel, Field
from starlette.responses import Response

from alfred.core.celery_client import get_celery_client
from alfred.core.dependencies import get_doc_storage_service
from alfred.core.exceptions import ServiceUnavailableError
from alfred.core.settings import settings
from alfred.services import notion
from alfred.services.doc_storage_pg import DocStorageService
from alfred.services.notion_import import import_notion_workspace
from alfred.services.notion_oauth import (
    exchange_code_for_token,
    generate_authorization_url,
    is_notion_oauth_configured,
    list_connected_workspaces,
    persist_oauth_token,
    revoke_oauth_token,
)
from alfred.services.oauth_callback_page import render_oauth_callback_page
from alfred.services.oauth_state import consume_oauth_state, save_oauth_state

router = APIRouter(prefix="/api/notion", tags=["notion"])
logger = logging.getLogger(__name__)


class NotionAuthUrlResponse(BaseModel):
    authorization_url: str
    state: str


class NotionImportRequest(BaseModel):
    workspace_id: str | None = None
    limit: int | None = Field(default=None, ge=1, le=10_000)
    since: str | None = None
    include_archived: bool = False
    run_inline: bool = False
    sleep_s: float = Field(default=0.35, ge=0.0, le=2.0)


class NotionImportStartResponse(BaseModel):
    status: str
    task_id: str | None = None
    status_url: str | None = None
    result: dict[str, Any] | None = None


@router.get("/status")
def notion_status() -> dict[str, Any]:
    env_token_present = bool(
        settings.notion_token is not None and settings.notion_token.get_secret_value().strip()
    )

    connected: list[dict[str, Any]] = []
    oauth_error: str | None = None
    if is_notion_oauth_configured():
        try:
            connected = list_connected_workspaces()
        except Exception as exc:
            oauth_error = str(exc)

    return {
        "env_token_present": env_token_present,
        "oauth_configured": is_notion_oauth_configured(),
        "secret_key_configured": bool(settings.secret_key is not None),
        "connected_workspaces": connected,
        "oauth_error": oauth_error,
    }


@router.get("/auth_url", response_model=NotionAuthUrlResponse)
def notion_auth_url(
    state: str | None = Query(default=None),
) -> dict[str, str]:
    """Generate a Notion OAuth URL."""

    url, st = generate_authorization_url(state=state)
    save_oauth_state(st, scopes=[], namespaces=[])
    return {"authorization_url": url, "state": st}


@router.get("/oauth/callback", response_model=None)
def notion_oauth_callback(
    code: str,
    state: str | None = None,
    json: bool = Query(default=False),
) -> Response:
    """Handle Notion OAuth callback and persist the encrypted token record."""

    try:
        if not state:
            raise ValueError("Missing OAuth state")
        if consume_oauth_state(state) is None:
            raise ValueError("OAuth state is invalid or expired")
        token = exchange_code_for_token(code=code)
        workspace = persist_oauth_token(token)
    except Exception as exc:
        if json:
            return JSONResponse(content={"ok": False, "error": str(exc)}, status_code=400)
        return HTMLResponse(
            content=render_oauth_callback_page(ok=False, message=str(exc), provider="notion"),
            status_code=400,
        )

    if json:
        return JSONResponse(content={"ok": True, "workspace": workspace}, status_code=200)

    return HTMLResponse(
        content=render_oauth_callback_page(
            ok=True, message="You can return to Alfred.", provider="notion"
        ),
        status_code=200,
    )


@router.post("/revoke")
def notion_revoke(workspace_id: str = Body(..., embed=True)) -> dict[str, Any]:
    """Delete a stored Notion OAuth token (does not affect NOTION_TOKEN)."""

    return {"ok": True, "removed": bool(revoke_oauth_token(workspace_id))}


@router.post("/import", response_model=NotionImportStartResponse)
def start_notion_import(
    payload: NotionImportRequest,
    svc: DocStorageService = Depends(get_doc_storage_service),
) -> NotionImportStartResponse:
    """Import Notion pages into Alfred documents (async by default)."""

    try:
        celery_client = get_celery_client()
        async_result = celery_client.send_task(
            "alfred.tasks.notion_import.import_workspace",
            kwargs={
                "workspace_id": payload.workspace_id,
                "limit": payload.limit,
                "since": payload.since,
                "include_archived": payload.include_archived,
                "sleep_s": payload.sleep_s,
            },
        )
        return NotionImportStartResponse(
            status="queued",
            task_id=async_result.id,
            status_url=f"/tasks/{async_result.id}",
        )
    except Exception as exc:
        if not payload.run_inline:
            raise HTTPException(status_code=500, detail="Failed to enqueue Notion import") from exc

    # Inline fallback for local/dev when Celery isn't running.
    result = import_notion_workspace(
        doc_store=svc,
        workspace_id=payload.workspace_id,
        limit=payload.limit,
        since=payload.since,
        include_archived=payload.include_archived,
        sleep_s=payload.sleep_s,
    )
    return NotionImportStartResponse(status="completed", result=result)


@router.get("/history", response_model=dict[str, Any])
async def get_notion_history(
    start_date: Optional[str] = Query(
        default=None,
        description="ISO 8601 date string; include pages edited on/after this value.",
    ),
    end_date: Optional[str] = Query(
        default=None,
        description="ISO 8601 date string; include pages edited on/before this value.",
    ),
    limit: Optional[int] = Query(
        default=10,
        ge=1,
        le=200,
        description="Maximum number of pages to return (default 10).",
    ),
    include_content: bool = Query(
        default=False,
        description="When true, fetch full block content for each page (slower).",
    ),
) -> Dict[str, Any]:
    try:
        pages = await notion.fetch_page_history(
            start_date=start_date,
            end_date=end_date,
            limit=limit,
            include_content=include_content,
        )
        return {"success": True, "count": len(pages), "pages": pages}
    except HTTPException as http_exc:
        raise http_exc
    except RuntimeError as rt_exc:
        logger.exception("Notion dependency failed")
        raise ServiceUnavailableError("Notion service unavailable") from rt_exc
    except Exception as exc:  # pragma: no cover - unexpected runtime errors
        logger.exception("Notion history failed")
        raise ServiceUnavailableError("Notion history failed") from exc
