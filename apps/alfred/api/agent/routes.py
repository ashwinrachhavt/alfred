"""Agent chat routes -- SSE streaming + thread management."""

from __future__ import annotations

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
    active_lens: str | None = None
    model_used: str | None = None
    created_at: Any = None


@router.post("/stream")
async def agent_stream(
    body: AgentStreamRequest,
    request: Request,
    db: Session = Depends(get_db_session),
):
    """SSE endpoint for agentic chat. Client closes connection to abort."""
    service = AgentService(db)

    thread_id = body.thread_id

    # Get-or-create thread by note_id when no explicit thread_id given
    if not thread_id and body.note_context and body.note_context.get("note_id"):
        note_id = body.note_context["note_id"]
        existing = db.exec(
            select(ThinkingSessionRow)
            .where(ThinkingSessionRow.note_id == note_id)
            .where(ThinkingSessionRow.session_type == "agent")
        ).first()
        if existing:
            thread_id = existing.id
        else:
            new_thread = ThinkingSessionRow(
                title=body.note_context.get("title", "Note conversation"),
                session_type="agent",
                status="active",
                note_id=note_id,
            )
            db.add(new_thread)
            db.commit()
            db.refresh(new_thread)
            thread_id = new_thread.id

    history = body.history
    if thread_id and not history:
        stmt = (
            select(AgentMessageRow)
            .where(AgentMessageRow.thread_id == thread_id)
            .order_by(AgentMessageRow.created_at.desc())
            .limit(20)
        )
        db_messages = db.exec(stmt).all()
        history = [{"role": m.role, "content": m.content} for m in reversed(db_messages)]

    async def event_stream():
        async for event in service.stream_turn(
            message=body.message,
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
            yield event

        # Update thread timestamp after streaming completes
        if thread_id:
            session = db.get(ThinkingSessionRow, thread_id)
            if session:
                session.updated_at = datetime.utcnow()
                db.add(session)
                db.commit()

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
    )


@router.post("/threads", status_code=status.HTTP_201_CREATED)
def create_thread(body: ThreadCreateRequest, db: Session = Depends(get_db_session)) -> ThreadSummary:
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
        .offset(skip).limit(limit)
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
        select(AgentMessageRow).where(AgentMessageRow.thread_id == thread_id).order_by(AgentMessageRow.created_at)
    ).all()

    return {
        "thread": _to_summary(session, message_count=len(messages)),
        "messages": [
            MessageOut(
                id=m.id, role=m.role, content=m.content, tool_calls=m.tool_calls,
                artifacts=m.artifacts, related_cards=m.related_cards, gaps=m.gaps,
                active_lens=m.active_lens, model_used=m.model_used, created_at=m.created_at,
            )
            for m in messages
        ],
    }


@router.patch("/threads/{thread_id}")
def update_thread(thread_id: int, body: ThreadUpdateRequest, db: Session = Depends(get_db_session)) -> ThreadSummary:
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


def _to_summary(session: ThinkingSessionRow, message_count: int = 0) -> ThreadSummary:
    return ThreadSummary(
        id=session.id, title=session.title, status=session.status,
        pinned=session.pinned, active_lens=session.active_lens,
        model_id=session.model_id, note_id=session.note_id,
        created_at=session.created_at, updated_at=session.updated_at,
        message_count=message_count,
    )
