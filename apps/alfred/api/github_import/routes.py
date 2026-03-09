from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from alfred.core.dependencies import get_doc_storage_service
from alfred.core.settings import settings
from alfred.schemas.imports import ImportResponse
from alfred.services.doc_storage_pg import DocStorageService
from alfred.services.github_import import (
    import_discussions,
    import_gists,
    import_github,
    import_starred,
)

router = APIRouter(prefix="/api/github/import", tags=["github"])
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------


class GitHubImportRequest(BaseModel):
    repos: list[str] = Field(default_factory=list)
    state: str | None = None
    since: str | None = None
    run_inline: bool = False


class StarredImportRequest(BaseModel):
    limit: int | None = Field(default=None, ge=1, le=10_000)
    run_inline: bool = False


class GistsImportRequest(BaseModel):
    since: str | None = None
    limit: int | None = Field(default=None, ge=1, le=10_000)
    run_inline: bool = False


class DiscussionsImportRequest(BaseModel):
    repos: list[str] = Field(default_factory=list)
    limit: int | None = Field(default=None, ge=1, le=10_000)
    run_inline: bool = False


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.post("", response_model=ImportResponse)
def start_import(
    payload: GitHubImportRequest,
    svc: DocStorageService = Depends(get_doc_storage_service),
) -> ImportResponse:
    """Import issues/PRs from GitHub repositories."""
    try:
        result = import_github(
            doc_store=svc,
            repos=payload.repos,
            state=payload.state,
            since=payload.since,
        )
    except Exception as exc:
        logger.exception("GitHub import failed")
        return ImportResponse(status="error", result={"ok": False, "error": str(exc)})
    return ImportResponse(status="completed", result=result)


@router.post("/starred", response_model=ImportResponse)
def start_starred_import(
    payload: StarredImportRequest,
    svc: DocStorageService = Depends(get_doc_storage_service),
) -> ImportResponse:
    """Import starred repositories from GitHub."""
    try:
        result = import_starred(
            doc_store=svc,
            limit=payload.limit,
        )
    except Exception as exc:
        logger.exception("GitHub starred import failed")
        return ImportResponse(status="error", result={"ok": False, "error": str(exc)})
    return ImportResponse(status="completed", result=result)


@router.post("/gists", response_model=ImportResponse)
def start_gists_import(
    payload: GistsImportRequest,
    svc: DocStorageService = Depends(get_doc_storage_service),
) -> ImportResponse:
    """Import gists from GitHub."""
    try:
        result = import_gists(
            doc_store=svc,
            since=payload.since,
            limit=payload.limit,
        )
    except Exception as exc:
        logger.exception("GitHub gists import failed")
        return ImportResponse(status="error", result={"ok": False, "error": str(exc)})
    return ImportResponse(status="completed", result=result)


@router.post("/discussions", response_model=ImportResponse)
def start_discussions_import(
    payload: DiscussionsImportRequest,
    svc: DocStorageService = Depends(get_doc_storage_service),
) -> ImportResponse:
    """Import discussions from GitHub repositories."""
    try:
        result = import_discussions(
            doc_store=svc,
            repos=payload.repos,
            limit=payload.limit,
        )
    except Exception as exc:
        logger.exception("GitHub discussions import failed")
        return ImportResponse(status="error", result={"ok": False, "error": str(exc)})
    return ImportResponse(status="completed", result=result)


@router.get("/status")
def github_status() -> dict[str, Any]:
    """Check if GitHub integration is configured."""
    configured = bool(
        settings.github_token is not None
        and settings.github_token.get_secret_value().strip()
    )
    return {"configured": configured}
