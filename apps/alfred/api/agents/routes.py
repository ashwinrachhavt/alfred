from __future__ import annotations

import logging
from datetime import date, datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from alfred.api.dependencies import require_internal_agent
from alfred.schemas.documents import DocumentIngest
from alfred.services.doc_storage import DocStorageService

router = APIRouter(
    prefix="/internal/agents",
    tags=["internal-agents"],
    dependencies=[Depends(require_internal_agent)],
)
logger = logging.getLogger(__name__)


def get_doc_storage_service() -> DocStorageService:
    return DocStorageService()


class IngestResponse(BaseModel):
    id: str
    duplicate: bool
    chunk_count: int
    chunk_ids: list[str]


@router.post(
    "/ingest",
    response_model=IngestResponse,
    status_code=status.HTTP_201_CREATED,
)
def ingest_document(
    payload: DocumentIngest,
    svc: DocStorageService = Depends(get_doc_storage_service),
) -> IngestResponse:
    try:
        result = svc.ingest_document(payload)
        return IngestResponse(**result)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # pragma: no cover - external IO
        logger.exception("Internal ingest failed: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to ingest document") from exc


class DailyDigestRequest(BaseModel):
    date: Optional[date] = Field(
        default=None,
        description="Date (YYYY-MM-DD) to summarize; defaults to today (UTC).",
    )
    limit: int = Field(default=20, ge=1, le=200)


class DailyDigestItem(BaseModel):
    id: str
    title: Optional[str] = None
    source_url: Optional[str] = None
    canonical_url: Optional[str] = None
    topics: Optional[dict[str, Any]] = None
    captured_at: Optional[datetime] = None
    tokens: Optional[int] = None
    summary: Optional[str] = None


class DailyDigestResponse(BaseModel):
    date: str
    summary: str
    total: int
    items: list[DailyDigestItem]


def _summarize_items(items: list[dict[str, Any]], *, limit: int = 5) -> str:
    lines = []
    for i, it in enumerate(items[:limit], start=1):
        title = it.get("title") or ""
        src = it.get("source_url") or it.get("canonical_url") or ""
        label = title[:120] if title else "(untitled)"
        lines.append(f"{i}. {label}{' — ' + src if src else ''}")
    if not lines:
        return "No documents ingested for this day."
    return "Daily digest:\n" + "\n".join(lines)


@router.post("/daily-digest", response_model=DailyDigestResponse)
def daily_digest(
    payload: DailyDigestRequest,
    svc: DocStorageService = Depends(get_doc_storage_service),
) -> DailyDigestResponse:
    target_date = payload.date or datetime.now(timezone.utc).date()
    date_str = target_date.isoformat()
    try:
        data = svc.list_documents(date=date_str, limit=payload.limit)
        summary = _summarize_items(data.get("items", []))
        items = [DailyDigestItem(**item) for item in data.get("items", [])]
        return DailyDigestResponse(
            date=date_str,
            summary=summary,
            total=data.get("total", 0),
            items=items,
        )
    except Exception as exc:  # pragma: no cover - external IO
        logger.exception("Daily digest failed: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to generate daily digest") from exc
