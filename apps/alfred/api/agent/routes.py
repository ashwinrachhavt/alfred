"""Agent chat routes -- SSE streaming + thread management.

The route owns thread lifecycle and message persistence.
The AgentService owns streaming, tool calls, and SSE event formatting.
"""

from __future__ import annotations

import json
import logging
import time
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlmodel import Session, select

from alfred.api.dependencies import get_db_session
from alfred.core.settings import settings
from alfred.models.thinking import AgentMessageRow, ThinkingSessionRow
from alfred.services.agent.service import AgentService
from alfred.services.knowledge_notifications import (
    get_notification_count,
    get_pending_notifications,
)
from alfred.streaming.producers.agent_producer import AgentProducer
from alfred.streaming.projectors import _parts as _parts_helpers
from alfred.streaming.projectors.message_row import MessageProjector
from alfred.streaming.projectors.snapshot import SnapshotProjector
from alfred.streaming.projectors.wire_agui import AGUIProjector
from alfred.streaming.recorder import RunRecorder

router = APIRouter(prefix="/api/agent", tags=["agent"])
logger = logging.getLogger(__name__)


class AgentStreamRequest(BaseModel):
    message: str
    thread_id: int | None = None
    note_context: dict | None = None  # {note_id, title, content_preview}
    history: list[dict[str, str]] | None = None
    lens: str | None = None
    model: str | None = None
    intent: str | None = None
    intent_args: dict | None = None
    max_iterations: int = 10


class ThreadCreateRequest(BaseModel):
    title: str | None = None


class ThreadUpdateRequest(BaseModel):
    title: str | None = None
    status: str | None = None
    pinned: bool | None = None


class ThreadSummary(BaseModel):
    id: int
    title: str | None
    status: str
    pinned: bool
    active_lens: str | None = None
    model_id: str | None = None
    note_id: str | None = None
    created_at: Any = None
    updated_at: Any = None
    message_count: int = 0


class MessageOut(BaseModel):
    id: int
    role: str
    content: str
    tool_calls: list | None = None
    artifacts: list | None = None
    related_cards: list | None = None
    gaps: list | None = None
    reasoning: str | None = None
    parts: list | None = None
    active_lens: str | None = None
    model_used: str | None = None
    created_at: Any = None


def _get_or_create_thread(
    db: Session,
    thread_id: int | None,
    note_context: dict | None,
    message: str,
    lens: str | None = None,
    model: str | None = None,
) -> int:
    """Get an existing thread or auto-create one. Always returns a thread_id."""

    # 1. Explicit thread_id — use it
    if thread_id:
        return thread_id

    # 2. Note context — find or create thread for this note
    if note_context and note_context.get("note_id"):
        note_id = note_context["note_id"]
        existing = db.exec(
            select(ThinkingSessionRow)
            .where(ThinkingSessionRow.note_id == note_id)
            .where(ThinkingSessionRow.session_type == "agent")
        ).first()
        if existing:
            return existing.id
        new_thread = ThinkingSessionRow(
            title=note_context.get("title", "Note conversation"),
            session_type="agent",
            status="active",
            note_id=note_id,
            active_lens=lens,
            model_id=model,
        )
        db.add(new_thread)
        db.commit()
        db.refresh(new_thread)
        return new_thread.id

    # 3. No thread, no note — auto-create a thread from the message
    title = message[:80].strip() if message else "New conversation"
    new_thread = ThinkingSessionRow(
        title=title,
        session_type="agent",
        status="active",
        active_lens=lens,
        model_id=model,
    )
    db.add(new_thread)
    db.commit()
    db.refresh(new_thread)
    return new_thread.id


def _persist_message(
    db: Session,
    thread_id: int,
    role: str,
    content: str,
    *,
    tool_calls: list | None = None,
    artifacts: list | None = None,
    related_cards: list | None = None,
    gaps: list | None = None,
    reasoning: str | None = None,
    parts: list | None = None,
    lens: str | None = None,
    model: str | None = None,
) -> AgentMessageRow:
    """Write a message to the database."""
    msg = AgentMessageRow(
        thread_id=thread_id,
        role=role,
        content=content,
        reasoning_traces=reasoning,
        tool_calls=tool_calls,
        artifacts=artifacts,
        related_cards=related_cards,
        gaps=gaps,
        parts=parts,
        active_lens=lens,
        model_used=model,
    )
    db.add(msg)
    db.commit()
    db.refresh(msg)
    return msg


def _handle_event_for_parts(
    parts: list[dict[str, Any]],
    event_name: str,
    data: dict[str, Any],
) -> None:
    """Mirror agent-store.ts _handleSSEEvent parts construction into Python.

    Called for every SSE event as it streams through the v1 route so that a
    canonical AI Elements parts[] is assembled alongside the legacy fields.
    """
    now_ms = int(time.time() * 1000)
    if event_name == "token":
        _parts_helpers.handle_token(parts, data.get("content", "") or "")
    elif event_name == "reasoning":
        _parts_helpers.handle_reasoning(parts, data.get("content", "") or "", now_ms)
    elif event_name == "tool_start":
        _parts_helpers.handle_tool_start(
            parts,
            tool_name=str(data.get("tool", "")),
            call_id=str(data.get("call_id") or ""),
            args=data.get("args") if isinstance(data.get("args"), dict) else None,
            now_ms=now_ms,
        )
    elif event_name == "tool_result":
        _parts_helpers.handle_tool_result(
            parts,
            call_id=str(data.get("call_id") or ""),
            result=data.get("result"),
        )
    elif event_name == "error":
        _parts_helpers.handle_error(parts, str(data.get("message") or "Something went wrong."), now_ms)
    # All other events (plan, task_*, artifact, related, gaps, approval_required,
    # tool_end, thread_created, done) do not mutate parts[] — same as frontend.


def _finalize_streaming_parts(parts: list[dict[str, Any]], now_ms: int) -> None:
    """Close any trailing streaming text/reasoning parts."""
    _parts_helpers.finalize_streaming_parts(parts, now_ms)


def _sse_event(event: str, data: dict) -> str:
    """Format a single SSE event."""
    return f"event: {event}\ndata: {json.dumps(data, default=str)}\n\n"


@router.post("/stream")
async def agent_stream(
    body: AgentStreamRequest,
    request: Request,
    db: Session = Depends(get_db_session),
):
    """SSE endpoint for agentic chat using the flat tool-calling loop.

    Routes owns: thread lifecycle, message persistence, history loading.
    AgentService owns: streaming, tool calls, SSE event formatting.
    """
    # Validate: need either a message or an intent
    if not (body.message and body.message.strip()) and not body.intent:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Either message or intent is required.",
        )

    # Use message text or synthesize from intent for thread creation
    message_text = body.message or f"[intent: {body.intent}]"

    # Auto-create thread if needed
    thread_id = _get_or_create_thread(
        db,
        body.thread_id,
        body.note_context,
        message_text,
        lens=body.lens,
        model=body.model,
    )

    # Load history from DB (last 20 messages)
    history = body.history
    if not history:
        stmt = (
            select(AgentMessageRow)
            .where(AgentMessageRow.thread_id == thread_id)
            .order_by(AgentMessageRow.created_at.desc())
            .limit(20)
        )
        db_messages = db.exec(stmt).all()
        history = [{"role": m.role, "content": m.content} for m in reversed(db_messages)]

    # Persist user message immediately
    _persist_message(db, thread_id, "user", message_text, lens=body.lens, model=body.model)

    async def event_stream():
        yield _sse_event("thread_created", {"thread_id": thread_id})

        service = AgentService(db)
        assistant_content = ""
        last_done_data: dict[str, Any] = {}
        parts: list[dict[str, Any]] = []

        async for event_name, data, sse_str in service.stream_turn(
            message=message_text,
            thread_id=thread_id,
            history=history,
            lens=body.lens,
            model=body.model,
            note_context=body.note_context,
            is_disconnected=request.is_disconnected,
            intent=body.intent,
            intent_args=body.intent_args,
            max_iterations=body.max_iterations,
        ):
            # Forward SSE to client
            yield sse_str

            # Accumulate the canonical assistant content for the legacy column.
            if event_name == "token":
                assistant_content += data.get("content", "") or ""
            elif event_name == "done":
                last_done_data = data

            # Build parts[] the same way the frontend store does so the DB
            # row round-trips identically to what the client renders.
            _handle_event_for_parts(parts, event_name, data)

        # Close any still-streaming text/reasoning parts before persistence.
        # Defensive: parts[] is a dual-write side channel; corruption here must
        # not abort the legacy-column write.
        try:
            _finalize_streaming_parts(parts, int(time.time() * 1000))
            parts_to_write = parts or None
        except Exception:
            logger.exception("parts finalize failed for thread %s; persisting without parts", thread_id)
            parts_to_write = None

        # Persist assistant message using collected data
        try:
            if assistant_content or last_done_data.get("tool_calls") or last_done_data.get("artifacts"):
                _persist_message(
                    db,
                    thread_id,
                    "assistant",
                    assistant_content,
                    tool_calls=last_done_data.get("tool_calls"),
                    artifacts=last_done_data.get("artifacts"),
                    reasoning=last_done_data.get("reasoning"),
                    parts=parts_to_write,
                    lens=body.lens,
                    model=body.model,
                )
        except Exception:
            logger.exception("Failed to persist assistant message for thread %s", thread_id)

        # Update thread timestamp
        try:
            session_row = db.get(ThinkingSessionRow, thread_id)
            if session_row:
                session_row.updated_at = datetime.utcnow()
                db.add(session_row)
                db.commit()
        except Exception:
            logger.exception("Failed to update thread timestamp for %s", thread_id)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/stream/v2")
async def agent_stream_v2(
    body: AgentStreamRequest,
    request: Request,
    db: Session = Depends(get_db_session),
):
    """AG-UI streaming endpoint — Phase 1 of streaming revamp.

    Feature-flagged: returns 404 when ``settings.streaming_v2_enabled`` is False.

    Dual-writes ``AgentMessageRow`` via ``MessageProjector`` (same schema shape
    as the legacy ``/stream`` route) plus the full typed event log to
    ``agent_run_events``.
    """
    if not settings.streaming_v2_enabled:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="streaming v2 disabled")

    if not (body.message and body.message.strip()) and not body.intent:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Either message or intent is required.",
        )

    message_text = body.message or f"[intent: {body.intent}]"

    thread_id = _get_or_create_thread(
        db, body.thread_id, body.note_context, message_text,
        lens=body.lens, model=body.model,
    )

    # Load history from DB if the client didn't provide one — mirrors v1.
    history = body.history
    if not history:
        stmt = (
            select(AgentMessageRow)
            .where(AgentMessageRow.thread_id == thread_id)
            .order_by(AgentMessageRow.created_at.desc())
            .limit(20)
        )
        db_messages = db.exec(stmt).all()
        history = [{"role": m.role, "content": m.content} for m in reversed(db_messages)]

    # Persist user message immediately — same contract as v1.
    _persist_message(db, thread_id, "user", message_text, lens=body.lens, model=body.model)

    service = AgentService(db)
    producer = AgentProducer(
        service=service,
        message=message_text,
        thread_id=thread_id,
        model=body.model,
        lens=body.lens,
        history=history,
        note_context=body.note_context,
        intent=body.intent,
        intent_args=body.intent_args,
        max_iterations=body.max_iterations,
    )
    recorder = RunRecorder.start(
        db, run_type="chat_turn",
        thread_id=thread_id,
        model_id=body.model,
        active_lens=body.lens,
        input_summary=message_text[:400] if message_text else None,
    )
    message_projector = MessageProjector(session=db)
    snapshot_projector = SnapshotProjector(session=db)
    wire = AGUIProjector()
    recorder.attach(message_projector)
    recorder.attach(snapshot_projector)

    async def event_stream():
        try:
            async with recorder:
                async for evt in producer.stream():
                    recorded = await recorder.emit_raw(evt)
                    for frame in wire.frames_for(recorded):
                        yield _format_agui_sse(frame, recorded.seq)
                    if await request.is_disconnected():
                        break
        except Exception:
            logger.exception("v2 stream failed")

        # Update thread timestamp — same tail as v1.
        try:
            session_row = db.get(ThinkingSessionRow, thread_id)
            if session_row:
                session_row.updated_at = datetime.utcnow()
                db.add(session_row)
                db.commit()
        except Exception:
            logger.exception("Failed to update thread timestamp for %s", thread_id)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


def _format_agui_sse(frame: dict, seq: int) -> str:
    """Format an AG-UI frame as an SSE event line per spec section 7.1."""
    payload = json.dumps(frame.get("data", {}), separators=(",", ":"), default=str)
    return f"event: {frame['event']}\nid: {seq}\ndata: {payload}\n\n"


@router.post("/threads", status_code=status.HTTP_201_CREATED)
def create_thread(
    body: ThreadCreateRequest, db: Session = Depends(get_db_session)
) -> ThreadSummary:
    session = ThinkingSessionRow(
        title=body.title or "New conversation",
        session_type="agent",
        status="active",
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return _to_summary(session)


@router.get("/threads")
def list_threads(
    status_filter: str = "active",
    note_id: str | None = None,
    limit: int = 50,
    skip: int = 0,
    db: Session = Depends(get_db_session),
) -> list[ThreadSummary]:
    from sqlalchemy import func as sa_func

    count_sub = (
        select(sa_func.count(AgentMessageRow.id))
        .where(AgentMessageRow.thread_id == ThinkingSessionRow.id)
        .correlate(ThinkingSessionRow)
        .scalar_subquery()
    )
    stmt = (
        select(ThinkingSessionRow, count_sub.label("message_count"))
        .where(ThinkingSessionRow.session_type == "agent")
        .where(ThinkingSessionRow.status == status_filter)
        .order_by(ThinkingSessionRow.updated_at.desc())
        .offset(skip)
        .limit(limit)
    )
    if note_id is not None:
        stmt = stmt.where(ThinkingSessionRow.note_id == note_id)

    rows = db.exec(stmt).all()
    results = []
    for session_row, msg_count in rows:
        summary = _to_summary(session_row)
        summary.message_count = msg_count
        results.append(summary)
    return results


@router.get("/threads/{thread_id}")
def get_thread(thread_id: int, db: Session = Depends(get_db_session)) -> dict[str, Any]:
    session = db.get(ThinkingSessionRow, thread_id)
    if not session or session.session_type != "agent":
        raise HTTPException(status_code=404, detail="Thread not found")

    messages = db.exec(
        select(AgentMessageRow)
        .where(AgentMessageRow.thread_id == thread_id)
        .order_by(AgentMessageRow.created_at)
    ).all()

    return {
        "thread": _to_summary(session, message_count=len(messages)),
        "messages": [
            MessageOut(
                id=m.id,
                role=m.role,
                content=m.content,
                tool_calls=m.tool_calls,
                artifacts=m.artifacts,
                related_cards=m.related_cards,
                gaps=m.gaps,
                reasoning=m.reasoning_traces,
                parts=m.parts,
                active_lens=m.active_lens,
                model_used=m.model_used,
                created_at=m.created_at,
            )
            for m in messages
        ],
    }


@router.patch("/threads/{thread_id}")
def update_thread(
    thread_id: int, body: ThreadUpdateRequest, db: Session = Depends(get_db_session)
) -> ThreadSummary:
    session = db.get(ThinkingSessionRow, thread_id)
    if not session or session.session_type != "agent":
        raise HTTPException(status_code=404, detail="Thread not found")
    if body.title is not None:
        session.title = body.title
    if body.status is not None:
        session.status = body.status
    if body.pinned is not None:
        session.pinned = body.pinned
    db.add(session)
    db.commit()
    db.refresh(session)
    return _to_summary(session)


@router.delete("/threads/{thread_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_thread(thread_id: int, db: Session = Depends(get_db_session)):
    session = db.get(ThinkingSessionRow, thread_id)
    if not session or session.session_type != "agent":
        raise HTTPException(status_code=404, detail="Thread not found")
    db.delete(session)
    db.commit()


@router.get("/notifications")
def get_notifications(limit: int = 10) -> dict[str, Any]:
    """Return pending knowledge notifications from Redis."""
    notifications = get_pending_notifications(limit=limit)
    count = get_notification_count()
    return {
        "notifications": notifications,
        "remaining": count,
    }


@router.get("/notifications/count")
def get_notifications_count() -> dict[str, int]:
    """Return the count of pending knowledge notifications."""
    return {"count": get_notification_count()}


def _to_summary(session: ThinkingSessionRow, message_count: int = 0) -> ThreadSummary:
    return ThreadSummary(
        id=session.id,
        title=session.title,
        status=session.status,
        pinned=session.pinned,
        active_lens=session.active_lens,
        model_id=session.model_id,
        note_id=session.note_id,
        created_at=session.created_at,
        updated_at=session.updated_at,
        message_count=message_count,
    )
