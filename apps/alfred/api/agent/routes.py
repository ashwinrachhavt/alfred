"""Agent chat routes -- SSE streaming + thread management."""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from pydantic import BaseModel
from sqlmodel import Session, select

from alfred.api.dependencies import get_db_session
from alfred.models.thinking import AgentMessageRow, ThinkingSessionRow
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
    lens: str | None = None,
    model: str | None = None,
) -> AgentMessageRow:
    """Write a message to the database."""
    msg = AgentMessageRow(
        thread_id=thread_id,
        role=role,
        content=content,
        tool_calls=tool_calls,
        artifacts=artifacts,
        active_lens=lens,
        model_used=model,
    )
    db.add(msg)
    db.commit()
    db.refresh(msg)
    return msg


def _sanitize_for_json(obj: Any) -> Any:
    """Recursively convert LangChain message objects and other non-serializable types to plain dicts/strings."""
    if isinstance(obj, BaseMessage):
        return {"type": obj.type, "content": obj.content}
    if isinstance(obj, dict):
        return {k: _sanitize_for_json(v) for k, v in obj.items()}
    if isinstance(obj, list | tuple):
        return [_sanitize_for_json(item) for item in obj]
    if hasattr(obj, "model_dump"):
        return obj.model_dump()
    if hasattr(obj, "dict"):
        return obj.dict()
    return obj


class _LangChainEncoder(json.JSONEncoder):
    """JSON encoder that handles LangChain message objects and other non-serializable types."""

    def default(self, obj: Any) -> Any:
        if isinstance(obj, BaseMessage):
            return {"type": obj.type, "content": obj.content}
        # Handle pydantic models (v1 and v2)
        if hasattr(obj, "model_dump"):
            return obj.model_dump()
        if hasattr(obj, "dict"):
            return obj.dict()
        return super().default(obj)


def _sse_event(event: str, data: dict) -> str:
    """Format a single SSE event."""
    return f"event: {event}\ndata: {json.dumps(data, cls=_LangChainEncoder, default=str)}\n\n"


@router.post("/stream")
async def agent_stream(
    body: AgentStreamRequest,
    request: Request,
    db: Session = Depends(get_db_session),
):
    """SSE endpoint for agentic chat. Thread-free: auto-creates threads as needed."""
    # Auto-create thread if needed — no more manual thread management required
    thread_id = _get_or_create_thread(
        db,
        body.thread_id,
        body.note_context,
        body.message,
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
    _persist_message(db, thread_id, "user", body.message, lens=body.lens, model=body.model)

    async def event_stream():
        from alfred.agents.graph import build_alfred_graph

        yield _sse_event("thread_created", {"thread_id": thread_id})
        yield _sse_event("phase", {"phase": "routing", "message": "Understanding your request..."})

        graph = build_alfred_graph()

        # Build initial state from history
        initial_messages = []
        for m in (history or []):
            if m["role"] == "user":
                initial_messages.append(HumanMessage(content=m["content"]))
            else:
                initial_messages.append(AIMessage(content=m["content"]))
        initial_messages.append(HumanMessage(content=body.message))

        input_state = {
            "messages": initial_messages,
            "user_id": "",
            "intent": body.intent,
            "phase": "routing",
            "active_agents": [],
            "knowledge_results": [],
            "research_results": [],
            "connector_results": [],
            "enrichment_results": [],
            "final_response": None,
            "artifacts": [],
        }

        assistant_content = ""
        tool_calls_log: list[dict] = []
        artifacts_log: list[dict] = []

        try:
            async for event in graph.astream_events(input_state, version="v2"):
                if await request.is_disconnected():
                    break

                kind = event.get("event", "")

                if kind == "on_chat_model_stream":
                    chunk = event.get("data", {}).get("chunk")
                    if chunk and hasattr(chunk, "content") and chunk.content:
                        assistant_content += chunk.content
                        yield _sse_event("token", {"content": chunk.content})

                elif kind == "on_tool_start":
                    tool_name = event.get("name", "")
                    tool_input = _sanitize_for_json(event.get("data", {}).get("input", {}))
                    tool_calls_log.append({"tool": tool_name, "args": tool_input})
                    yield _sse_event("tool_start", {"tool": tool_name, "args": tool_input})

                elif kind == "on_tool_end":
                    tool_name = event.get("name", "")
                    raw_output = event.get("data", {}).get("output", "")
                    # Extract content string from LangChain ToolMessage/BaseMessage objects
                    if isinstance(raw_output, BaseMessage):
                        tool_output = raw_output.content[:500]
                    else:
                        tool_output = str(raw_output)[:500]
                    yield _sse_event("tool_result", {"tool": tool_name, "result": tool_output})

        except Exception as e:
            logger.exception("Graph streaming error")
            yield _sse_event("error", {"message": str(e)})

        yield _sse_event("done", {})

        # Persist assistant message
        if assistant_content or tool_calls_log or artifacts_log:
            _persist_message(
                db,
                thread_id,
                "assistant",
                assistant_content,
                tool_calls=tool_calls_log or None,
                artifacts=artifacts_log or None,
                lens=body.lens,
                model=body.model,
            )

        # Update thread timestamp
        session_row = db.get(ThinkingSessionRow, thread_id)
        if session_row:
            session_row.updated_at = datetime.utcnow()
            db.add(session_row)
            db.commit()

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
