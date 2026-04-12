"""Agent chat routes -- SSE streaming + thread management.

The route owns thread lifecycle and message persistence.
The AgentService owns streaming, tool calls, and SSE event formatting.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlmodel import Session, select

from alfred.api.dependencies import get_db_session
from alfred.models.thinking import AgentMessageRow, ThinkingSessionRow
from alfred.services.agent.service import AgentService
from alfred.services.knowledge_notifications import (
    get_notification_count,
    get_pending_notifications,
)

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
        active_lens=lens,
        model_used=model,
    )
    db.add(msg)
    db.commit()
    db.refresh(msg)
    return msg


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

            # Collect content for persistence
            if event_name == "token":
                assistant_content += data.get("content", "")
            elif event_name == "done":
                last_done_data = data

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
    stmt = (
        select(ThinkingSessionRow)
        .where(ThinkingSessionRow.session_type == "agent")
        .where(ThinkingSessionRow.status == status_filter)
        .order_by(ThinkingSessionRow.updated_at.desc())
        .offset(skip)
        .limit(limit)
    )
    if note_id is not None:
        stmt = stmt.where(ThinkingSessionRow.note_id == note_id)
    sessions = db.exec(stmt).all()
    results = []
    for s in sessions:
        count = len(db.exec(select(AgentMessageRow).where(AgentMessageRow.thread_id == s.id)).all())
        summary = _to_summary(s)
        summary.message_count = count
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
