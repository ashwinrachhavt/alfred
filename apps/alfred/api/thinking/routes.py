"""API routes for thinking canvas sessions."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session

from alfred.api.dependencies import get_db_session
from alfred.schemas.thinking import (
    DecomposeRequest,
    DecomposeResponse,
    ThinkingSessionCreate,
    ThinkingSessionResponse,
    ThinkingSessionSummary,
    ThinkingSessionUpdate,
)
from alfred.services.thinking_session_service import ThinkingSessionService

router = APIRouter(prefix="/api/thinking", tags=["thinking"])


@router.post(
    "/sessions",
    response_model=ThinkingSessionResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_session(
    payload: ThinkingSessionCreate,
    session: Session = Depends(get_db_session),
) -> ThinkingSessionResponse:
    service = ThinkingSessionService(session)
    return service.create_session(payload)


@router.get("/sessions", response_model=list[ThinkingSessionSummary])
def list_sessions(
    status_filter: str | None = None,
    limit: int = 50,
    skip: int = 0,
    session: Session = Depends(get_db_session),
) -> list[ThinkingSessionSummary]:
    service = ThinkingSessionService(session)
    return service.list_sessions(status=status_filter, limit=limit, skip=skip)


@router.get("/sessions/{session_id}", response_model=ThinkingSessionResponse)
def get_session(
    session_id: int,
    session: Session = Depends(get_db_session),
) -> ThinkingSessionResponse:
    service = ThinkingSessionService(session)
    result = service.get_session(session_id)
    if not result:
        raise HTTPException(status_code=404, detail="Thinking session not found")
    return result


@router.patch("/sessions/{session_id}", response_model=ThinkingSessionResponse)
def update_session(
    session_id: int,
    payload: ThinkingSessionUpdate,
    session: Session = Depends(get_db_session),
) -> ThinkingSessionResponse:
    service = ThinkingSessionService(session)
    result = service.update_session(session_id, payload)
    if not result:
        raise HTTPException(status_code=404, detail="Thinking session not found")
    return result


@router.patch("/sessions/{session_id}/archive", response_model=ThinkingSessionResponse)
def archive_session(
    session_id: int,
    session: Session = Depends(get_db_session),
) -> ThinkingSessionResponse:
    service = ThinkingSessionService(session)
    result = service.archive_session(session_id)
    if not result:
        raise HTTPException(status_code=404, detail="Thinking session not found")
    return result


@router.post(
    "/sessions/{session_id}/fork",
    response_model=ThinkingSessionResponse,
    status_code=status.HTTP_201_CREATED,
)
def fork_session(
    session_id: int,
    session: Session = Depends(get_db_session),
) -> ThinkingSessionResponse:
    service = ThinkingSessionService(session)
    try:
        return service.fork_session(session_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Thinking session not found") from exc


@router.post("/decompose", response_model=DecomposeResponse)
def decompose(payload: DecomposeRequest) -> DecomposeResponse:
    """Stub endpoint for AI decomposition — returns empty blocks for now."""
    return DecomposeResponse(blocks=[])
