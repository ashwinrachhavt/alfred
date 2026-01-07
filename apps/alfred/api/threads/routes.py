from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, Query

from alfred.schemas.threads import Thread, ThreadCreate, ThreadMessage, ThreadMessageCreate
from alfred.services.thread_service import ThreadNotFoundError, ThreadService

router = APIRouter(prefix="/api/threads", tags=["threads"])


def _as_uuid(value: str) -> uuid.UUID:
    try:
        return uuid.UUID(value)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Invalid thread id: {value}") from exc


def _thread_to_schema(row) -> Thread:
    return Thread(
        id=str(row.id),
        kind=row.kind,
        title=row.title,
        user_id=row.user_id,
        metadata=row.meta or {},
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _message_to_schema(row) -> ThreadMessage:
    return ThreadMessage(
        id=str(row.id),
        thread_id=str(row.thread_id),
        role=row.role,
        content=row.content,
        data=row.data or {},
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


@router.get("", response_model=list[Thread])
def list_threads(
    kind: str | None = Query(default=None),
    user_id: int | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> list[Thread]:
    svc = ThreadService()
    rows = svc.list_threads(kind=kind, user_id=user_id, limit=limit, offset=offset)
    return [_thread_to_schema(r) for r in rows]


@router.post("", response_model=Thread)
def create_thread(payload: ThreadCreate) -> Thread:
    svc = ThreadService()
    row = svc.upsert_thread(
        kind=payload.kind,
        title=payload.title,
        user_id=payload.user_id,
        metadata=payload.metadata,
    )
    return _thread_to_schema(row)


@router.get("/{thread_id}", response_model=Thread)
def get_thread(thread_id: str) -> Thread:
    svc = ThreadService()
    try:
        row = svc.get_thread(_as_uuid(thread_id))
    except ThreadNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _thread_to_schema(row)


@router.get("/{thread_id}/messages", response_model=list[ThreadMessage])
def list_messages(
    thread_id: str,
    limit: int = Query(default=200, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
) -> list[ThreadMessage]:
    svc = ThreadService()
    try:
        rows = svc.list_messages(thread_id=_as_uuid(thread_id), limit=limit, offset=offset)
    except ThreadNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return [_message_to_schema(r) for r in rows]


@router.post("/{thread_id}/messages", response_model=ThreadMessage)
def append_message(thread_id: str, payload: ThreadMessageCreate) -> ThreadMessage:
    svc = ThreadService()
    try:
        row = svc.append_message(
            thread_id=_as_uuid(thread_id),
            role=payload.role,
            content=payload.content,
            data=payload.data,
        )
    except ThreadNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _message_to_schema(row)
