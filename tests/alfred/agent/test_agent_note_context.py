"""Tests for agent routes — note_context, thread filtering, and thread summary."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import StaticPool
from sqlmodel import Session, create_engine, select

from alfred.api.agent.routes import router as agent_router
from alfred.api.dependencies import get_db_session
from alfred.models.thinking import AgentMessageRow, ThinkingSessionRow

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def db_session():
    """In-memory SQLite session with only the tables we need."""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    # Create only the tables for models we use
    ThinkingSessionRow.metadata.create_all(
        engine,
        tables=[
            ThinkingSessionRow.__table__,
            AgentMessageRow.__table__,
        ],
    )
    with Session(engine) as session:
        yield session


@pytest.fixture()
def app_and_client(db_session: Session):
    """FastAPI app + TestClient wired to the in-memory session."""
    app = FastAPI()
    app.include_router(agent_router)

    def _override_db():
        yield db_session

    app.dependency_overrides[get_db_session] = _override_db
    client = TestClient(app)
    return app, client, db_session


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_stream_request_accepts_note_context(app_and_client):
    """POST /api/agent/stream with note_context returns a streaming response (200)."""
    app, client, _ = app_and_client

    async def _fake_stream_turn(**kwargs):
        yield ("token", {"content": "Note-aware response"}, 'event: token\ndata: {"content": "Note-aware response"}\n\n')
        yield ("done", {"thread_id": "1", "reasoning": None, "tool_calls": None, "artifacts": None}, 'event: done\ndata: {"thread_id": "1"}\n\n')

    with patch("alfred.api.agent.routes.AgentService") as MockService:
        instance = MagicMock()
        instance.stream_turn = _fake_stream_turn
        MockService.return_value = instance

        resp = client.post(
            "/api/agent/stream",
            json={
                "message": "Summarize this note",
                "note_context": {
                    "note_id": "note-123",
                    "title": "My Research Note",
                    "content_preview": "This note is about...",
                },
            },
        )

        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/event-stream")


def test_stream_request_accepts_document_source_context(app_and_client, monkeypatch):
    """Document-scoped chat creates/reuses a source-bound thread and passes context."""
    _, client, session = app_and_client
    captured: dict = {}

    async def _fake_stream_turn(**kwargs):
        captured.update(kwargs)
        yield ("token", {"content": "Document-aware response"}, 'event: token\ndata: {"content": "Document-aware response"}\n\n')
        yield ("done", {"thread_id": "1", "reasoning": None, "tool_calls": None, "artifacts": None}, 'event: done\ndata: {"thread_id": "1"}\n\n')

    monkeypatch.setattr(
        "alfred.api.agent.routes._document_context_for_source",
        lambda source_context: "Document: The Smile Curve\nKind: blog_article",
    )

    with patch("alfred.api.agent.routes.AgentService") as MockService:
        instance = MagicMock()
        instance.stream_turn = _fake_stream_turn
        MockService.return_value = instance

        resp = client.post(
            "/api/agent/stream",
            json={
                "message": "What is the thesis?",
                "source_context": {
                    "source_kind": "document",
                    "source_id": "doc-123",
                    "title": "The Smile Curve",
                },
            },
        )

    assert resp.status_code == 200
    assert captured["source_context"] == "Document: The Smile Curve\nKind: blog_article"

    thread = session.exec(select(ThinkingSessionRow)).one()
    assert thread.source_kind == "document"
    assert thread.source_id == "doc-123"
    assert thread.title == "The Smile Curve"


def test_stream_persists_and_forwards_image_attachments(app_and_client):
    """Image attachments are saved on the user message and passed to the agent service."""
    _, client, session = app_and_client
    captured: dict = {}
    data_url = "data:image/png;base64,iVBORw0KGgo="

    async def _fake_stream_turn(**kwargs):
        captured.update(kwargs)
        yield ("done", {"thread_id": "1", "reasoning": None, "tool_calls": None, "artifacts": None}, 'event: done\ndata: {"thread_id": "1"}\n\n')

    with patch("alfred.api.agent.routes.AgentService") as MockService:
        instance = MagicMock()
        instance.stream_turn = _fake_stream_turn
        MockService.return_value = instance

        resp = client.post(
            "/api/agent/stream",
            json={
                "message": "What is in this screenshot?",
                "attachments": [
                    {
                        "kind": "image",
                        "name": "screen.png",
                        "mime_type": "image/png",
                        "size": 12,
                        "data_url": data_url,
                    }
                ],
            },
        )

    assert resp.status_code == 200
    assert captured["image_attachments"][0]["data_url"] == data_url

    messages = session.exec(select(AgentMessageRow)).all()
    user_message = next(message for message in messages if message.role == "user")
    assert user_message.parts == [
        {"type": "text", "text": "What is in this screenshot?", "state": "done"},
        {
            "type": "image",
            "url": data_url,
            "mimeType": "image/png",
            "name": "screen.png",
            "size": 12,
            "state": "done",
        },
    ]


def test_stream_rejects_unsupported_image_type(app_and_client):
    """Only browser-safe image attachments are accepted."""
    _, client, _ = app_and_client

    resp = client.post(
        "/api/agent/stream",
        json={
            "message": "Analyze this",
            "attachments": [
                {
                    "kind": "image",
                    "name": "vector.svg",
                    "mime_type": "image/svg+xml",
                    "size": 12,
                    "data_url": "data:image/svg+xml;base64,PHN2Zy8+",
                }
            ],
        },
    )

    assert resp.status_code == 415


def test_threads_filter_by_note_id(app_and_client):
    """GET /api/agent/threads?note_id=xxx returns empty list for non-existent note."""
    _, client, _ = app_and_client

    resp = client.get("/api/agent/threads", params={"note_id": "nonexistent-note-999"})
    assert resp.status_code == 200
    assert resp.json() == []


def test_threads_filter_by_note_id_returns_matching(app_and_client):
    """GET /api/agent/threads?note_id=xxx returns only threads for that note."""
    _, client, session = app_and_client

    thread_with_note = ThinkingSessionRow(
        title="Note thread",
        session_type="agent",
        status="active",
        note_id="note-abc",
    )
    thread_without_note = ThinkingSessionRow(
        title="General thread",
        session_type="agent",
        status="active",
        note_id=None,
    )
    session.add(thread_with_note)
    session.add(thread_without_note)
    session.commit()

    resp = client.get("/api/agent/threads", params={"note_id": "note-abc"})
    assert resp.status_code == 200

    data = resp.json()
    assert len(data) == 1
    assert data[0]["note_id"] == "note-abc"
    assert data[0]["title"] == "Note thread"


def test_threads_filter_by_source_context(app_and_client):
    """GET /api/agent/threads?source_kind=document&source_id=xxx returns matching threads."""
    _, client, session = app_and_client

    matching = ThinkingSessionRow(
        title="Document thread",
        session_type="agent",
        status="active",
        source_kind="document",
        source_id="doc-abc",
    )
    other = ThinkingSessionRow(
        title="Other thread",
        session_type="agent",
        status="active",
        source_kind="document",
        source_id="doc-other",
    )
    session.add(matching)
    session.add(other)
    session.commit()

    resp = client.get(
        "/api/agent/threads",
        params={"source_kind": "document", "source_id": "doc-abc"},
    )
    assert resp.status_code == 200

    data = resp.json()
    assert len(data) == 1
    assert data[0]["source_kind"] == "document"
    assert data[0]["source_id"] == "doc-abc"
    assert data[0]["title"] == "Document thread"


def test_thread_summary_includes_note_id(app_and_client):
    """Create a thread with note_id, verify note_id appears in the response."""
    _, client, session = app_and_client

    thread = ThinkingSessionRow(
        title="Note conversation",
        session_type="agent",
        status="active",
        note_id="note-xyz",
    )
    session.add(thread)
    session.commit()
    session.refresh(thread)

    resp = client.get(f"/api/agent/threads/{thread.id}")
    assert resp.status_code == 200

    data = resp.json()
    assert data["thread"]["note_id"] == "note-xyz"
    assert data["thread"]["title"] == "Note conversation"
    assert data["messages"] == []


def test_create_thread_returns_summary(app_and_client):
    """POST /api/agent/threads creates a thread and returns a summary."""
    _, client, _ = app_and_client

    resp = client.post("/api/agent/threads", json={"title": "Test thread"})
    assert resp.status_code == 201

    data = resp.json()
    assert data["title"] == "Test thread"
    assert data["status"] == "active"
    assert data["pinned"] is False
    assert data["note_id"] is None
    assert "id" in data


def test_list_threads_default_filter(app_and_client):
    """GET /api/agent/threads returns only active agent threads."""
    _, client, session = app_and_client

    active = ThinkingSessionRow(
        title="Active",
        session_type="agent",
        status="active",
    )
    archived = ThinkingSessionRow(
        title="Archived",
        session_type="agent",
        status="archived",
    )
    canvas = ThinkingSessionRow(
        title="Canvas",
        session_type="canvas",
        status="active",
    )
    session.add_all([active, archived, canvas])
    session.commit()

    resp = client.get("/api/agent/threads")
    assert resp.status_code == 200

    data = resp.json()
    titles = [t["title"] for t in data]
    assert "Active" in titles
    assert "Archived" not in titles
    assert "Canvas" not in titles
