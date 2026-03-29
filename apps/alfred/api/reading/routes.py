from __future__ import annotations

import logging
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from starlette.responses import StreamingResponse

from alfred.core.dependencies import get_reading_service
from alfred.core.exceptions import AlfredException
from alfred.services.reading_service import ReadingService

router = APIRouter(prefix="/api/reading", tags=["reading"])
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------


class TrackEvent(BaseModel):
    url: str
    title: str | None = None
    domain: str | None = None
    score: int = 0
    active_time_ms: int = 0
    scroll_depth: int = 0
    selection_count: int = 0
    copy_count: int = 0
    is_revisit: bool = False
    timestamp: str | None = None


class TrackRequest(BaseModel):
    events: list[TrackEvent]


class TrackResponse(BaseModel):
    received: int
    ingested: int


class IngestRequest(BaseModel):
    url: str
    title: str | None = None
    text: str = Field(..., min_length=50)
    html: str | None = None
    engagement_score: int = 0
    active_time_ms: int = 0
    scroll_depth: int = 0


class IngestResponse(BaseModel):
    document_id: str | None = None
    status: str


class CompanionRequest(BaseModel):
    url: str
    title: str | None = None
    text: str = Field(..., min_length=10)
    mode: Literal["connections", "decompose", "chat"]
    message: str | None = None
    chat_history: list[dict[str, str]] | None = None


class ConnectionItem(BaseModel):
    title: str | None = None
    source_url: str | None = None
    text: str | None = None


class ConnectionsResponse(BaseModel):
    connections: list[ConnectionItem]


class ClaimItem(BaseModel):
    text: str
    tag: str


class DecomposeResponse(BaseModel):
    summary: str
    claims: list[ClaimItem]
    open_questions: list[str]


class HistoryItem(BaseModel):
    id: str
    url: str
    title: str | None = None
    domain: str | None = None
    engagement_score: int = 0
    active_time_ms: int = 0
    scroll_depth: int = 0
    selection_count: int = 0
    copy_count: int = 0
    is_revisit: bool = False
    captured: bool = False
    document_id: str | None = None
    created_at: str | None = None


class HistoryResponse(BaseModel):
    items: list[HistoryItem]
    total: int


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/track", response_model=TrackResponse)
def track_reading(
    payload: TrackRequest,
    svc: ReadingService = Depends(get_reading_service),
) -> TrackResponse:
    """Receive a batch of reading engagement events from the extension."""
    try:
        result = svc.track_events([ev.model_dump() for ev in payload.events])
        return TrackResponse(**result)
    except AlfredException:
        raise
    except Exception as exc:  # pragma: no cover - external IO
        logger.exception("Failed to track reading events: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to track reading events") from exc


@router.post("/ingest", response_model=IngestResponse)
def ingest_page(
    payload: IngestRequest,
    svc: ReadingService = Depends(get_reading_service),
) -> IngestResponse:
    """Capture a high-engagement page into the document store."""
    try:
        result = svc.ingest_page(
            url=payload.url,
            title=payload.title,
            text=payload.text,
            html=payload.html,
            engagement_score=payload.engagement_score,
            active_time_ms=payload.active_time_ms,
            scroll_depth=payload.scroll_depth,
        )
        return IngestResponse(**result)
    except AlfredException:
        raise
    except Exception as exc:  # pragma: no cover - external IO
        logger.exception("Failed to ingest page: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to ingest page") from exc


@router.post("/companion")
async def companion(
    payload: CompanionRequest,
    svc: ReadingService = Depends(get_reading_service),
) -> Any:
    """AI companion endpoint — routes by mode (connections, decompose, chat)."""
    try:
        if payload.mode == "connections":
            connections = svc.get_connections(payload.text)
            return ConnectionsResponse(
                connections=[ConnectionItem(**c) for c in connections]
            )

        if payload.mode == "decompose":
            result = svc.decompose_article(payload.text, payload.title or "Untitled")
            return DecomposeResponse(
                summary=result.get("summary", ""),
                claims=[ClaimItem(**c) for c in result.get("claims", [])],
                open_questions=result.get("open_questions", []),
            )

        if payload.mode == "chat":
            if not payload.message:
                raise HTTPException(status_code=400, detail="message is required for chat mode")

            connections = svc.get_connections(payload.text, limit=3)

            return StreamingResponse(
                svc.chat_stream(
                    text=payload.text,
                    message=payload.message,
                    chat_history=payload.chat_history,
                    connections=connections,
                ),
                media_type="application/x-ndjson",
            )

        raise HTTPException(status_code=400, detail=f"Unknown mode: {payload.mode}")

    except HTTPException:
        raise
    except AlfredException:
        raise
    except Exception as exc:  # pragma: no cover - external IO
        logger.exception("Companion request failed: %s", exc)
        raise HTTPException(status_code=500, detail="Companion request failed") from exc


@router.get("/history", response_model=HistoryResponse)
def reading_history(
    limit: int = Query(20, ge=1, le=200),
    offset: int = Query(0, ge=0),
    domain: str | None = Query(None, description="Filter by domain"),
    min_score: int | None = Query(None, ge=0, le=100, description="Minimum engagement score"),
    svc: ReadingService = Depends(get_reading_service),
) -> HistoryResponse:
    """Query reading session history with optional filters."""
    try:
        result = svc.get_history(
            limit=limit,
            offset=offset,
            domain=domain,
            min_score=min_score,
        )
        return HistoryResponse(
            items=[HistoryItem(**item) for item in result["items"]],
            total=result["total"],
        )
    except AlfredException:
        raise
    except Exception as exc:  # pragma: no cover - external IO
        logger.exception("Failed to fetch reading history: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to fetch reading history") from exc
