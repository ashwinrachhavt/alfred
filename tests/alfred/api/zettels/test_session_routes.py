"""Tests for the T6 session routes."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel

from alfred.api.dependencies import get_db_session
from alfred.api.zettels.routes import router as zettels_router
from alfred.services.zettelkasten_service import ZettelkastenService


@pytest.fixture()
def db_session() -> Session:
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


@pytest.fixture()
def client(db_session: Session) -> TestClient:
    app = FastAPI()
    app.include_router(zettels_router)
    app.dependency_overrides[get_db_session] = lambda: db_session
    return TestClient(app)


# ---------------------------------------------------------------------------
# POST /api/zettels/sessions
# ---------------------------------------------------------------------------


def test_post_sessions_returns_201_with_session(client: TestClient) -> None:
    resp = client.post(
        "/api/zettels/sessions",
        json={
            "title": "Sitting on AI",
            "shared_topic": "ai",
            "shared_tags": ["llm", "rag"],
        },
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["id"] > 0
    assert body["title"] == "Sitting on AI"
    assert body["shared_topic"] == "ai"
    assert body["shared_tags"] == ["llm", "rag"]
    assert body["ended_at"] is None
    assert body["summary_card_id"] is None
    assert body["card_count"] == 0
    assert body["status"] == "active"


def test_post_sessions_minimal_body(client: TestClient) -> None:
    resp = client.post("/api/zettels/sessions", json={})
    assert resp.status_code == 201
    body = resp.json()
    assert body["id"] > 0
    assert body["title"] is None
    assert body["shared_topic"] is None
    assert body["shared_tags"] is None
    assert body["source_context"] is None
    assert body["status"] == "active"


# ---------------------------------------------------------------------------
# POST /api/zettels/sessions/{id}/end
# ---------------------------------------------------------------------------


def test_post_session_end_returns_session(client: TestClient) -> None:
    created = client.post("/api/zettels/sessions", json={"title": "empty"}).json()
    resp = client.post(f"/api/zettels/sessions/{created['id']}/end")
    assert resp.status_code == 200
    body = resp.json()
    assert body["ended_at"] is not None
    assert body["summary_card_id"] is None
    assert body["status"] == "abandoned"


def test_post_session_end_404_on_missing(client: TestClient) -> None:
    resp = client.post("/api/zettels/sessions/99999/end")
    assert resp.status_code == 404


def test_post_session_end_409_on_already_ended(client: TestClient) -> None:
    created = client.post("/api/zettels/sessions", json={"title": "twice"}).json()
    client.post(f"/api/zettels/sessions/{created['id']}/end")
    second = client.post(f"/api/zettels/sessions/{created['id']}/end")
    assert second.status_code == 409
    detail = second.json()["detail"]
    # detail is a dict with the existing session body so client can reconcile
    assert isinstance(detail, dict)
    assert detail["message"] == "Session already ended"
    assert detail["session"]["id"] == created["id"]
    assert detail["session"]["status"] == "abandoned"


# ---------------------------------------------------------------------------
# GET /api/zettels/sessions/{id}/hydrate
# ---------------------------------------------------------------------------


def test_get_session_hydrate_returns_full_plus_stubs(
    client: TestClient, db_session: Session
) -> None:
    created = client.post("/api/zettels/sessions", json={"title": "hydrate"}).json()

    # Seed 4 cards directly via the service (faster than HTTP, fine for the test).
    zsvc = ZettelkastenService(db_session)
    cards = [
        zsvc.create_card(title=f"C{i}", summary="s", session_id=created["id"]) for i in range(4)
    ]
    base = datetime.utcnow() - timedelta(days=1)
    for i, c in enumerate(cards):
        c.updated_at = base + timedelta(hours=i)
        db_session.add(c)
    db_session.commit()

    resp = client.get(f"/api/zettels/sessions/{created['id']}/hydrate")
    assert resp.status_code == 200
    body = resp.json()
    assert body["session"]["id"] == created["id"]
    assert len(body["full_cards"]) == 3
    assert len(body["stub_cards"]) == 1
    # Most recently updated card comes first in full_cards.
    assert body["full_cards"][0]["id"] == cards[3].id


def test_get_session_hydrate_404_on_missing(client: TestClient) -> None:
    resp = client.get("/api/zettels/sessions/99999/hydrate")
    assert resp.status_code == 404
