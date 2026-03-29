"""Tests for agent routes — note_context, thread filtering, and thread summary."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import StaticPool
from sqlmodel import Session, create_engine

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
    ThinkingSessionRow.metadata.create_all(engine, tables=[
        ThinkingSessionRow.__table__,
        AgentMessageRow.__table__,
    ])
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

    async def _fake_stream(**kwargs):
        yield "event: done\ndata: {}\n\n"

    with patch(
        "alfred.api.agent.routes.AgentService",
        autospec=True,
    ) as MockService:
        MockService.return_value.stream_turn = _fake_stream

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
        title="Active", session_type="agent", status="active",
    )
    archived = ThinkingSessionRow(
        title="Archived", session_type="agent", status="archived",
    )
    canvas = ThinkingSessionRow(
        title="Canvas", session_type="canvas", status="active",
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
