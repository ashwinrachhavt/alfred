"""Integration tests for ``/api/today/entries`` CRUD routes."""

from __future__ import annotations

from collections.abc import Generator
from datetime import date

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel

from alfred.api.dependencies import get_db_session
from alfred.api.today.routes import router as today_router


@pytest.fixture()
def session() -> Generator[Session, None, None]:
    """In-memory SQLite shared across threads.

    FastAPI's TestClient runs each request in a threadpool, so the default
    ``sqlite:///:memory:`` engine (which uses SingletonThreadPool + a fresh
    connection per thread) gives the test thread a different database than
    the request thread. ``StaticPool`` + ``check_same_thread=False`` pins a
    single connection and lets both threads see the same tables.
    """
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


@pytest.fixture()
def client(session: Session) -> TestClient:
    app = FastAPI()
    app.include_router(today_router)
    app.dependency_overrides[get_db_session] = lambda: session
    return TestClient(app)


_TODAY = "2026-04-30"


def _create(client: TestClient, **overrides) -> dict:
    body = {
        "entry_date": _TODAY,
        "kind": "todo",
        "title": "default title",
    }
    body.update(overrides)
    resp = client.post("/api/today/entries", json=body)
    assert resp.status_code == 201, resp.text
    return resp.json()


# ---------------------------------------------------------------------------
# POST /api/today/entries
# ---------------------------------------------------------------------------


def test_post_entries_creates_row_and_returns_201(client: TestClient) -> None:
    resp = client.post(
        "/api/today/entries",
        json={
            "entry_date": _TODAY,
            "kind": "todo",
            "title": "Ship T3",
            "body_md": "write the routes",
            "priority": 3,
            "tags": ["backend", "today"],
            "meta": {"source": "cli"},
        },
    )
    assert resp.status_code == 201
    body = resp.json()
    assert isinstance(body["id"], int)
    assert body["kind"] == "todo"
    assert body["title"] == "Ship T3"
    assert body["body_md"] == "write the routes"
    assert body["status"] == "open"
    assert body["priority"] == 3
    assert body["tags"] == ["backend", "today"]
    assert body["meta"] == {"source": "cli"}
    assert body["is_synthetic"] is False
    assert body["entry_date"] == _TODAY


def test_post_entries_rejects_artifact_ref_kind_with_422(client: TestClient) -> None:
    resp = client.post(
        "/api/today/entries",
        json={"entry_date": _TODAY, "kind": "artifact_ref", "title": "nope"},
    )
    assert resp.status_code == 422
    assert "artifact_ref" in resp.text


def test_post_entries_rejects_invalid_kind_with_422(client: TestClient) -> None:
    resp = client.post(
        "/api/today/entries",
        json={"entry_date": _TODAY, "kind": "invalid", "title": "nope"},
    )
    assert resp.status_code == 422
    assert "invalid kind" in resp.text


def test_post_entries_rejects_bogus_status_with_422(client: TestClient) -> None:
    resp = client.post(
        "/api/today/entries",
        json={
            "entry_date": _TODAY,
            "kind": "todo",
            "title": "ok",
            "status": "bogus",
        },
    )
    assert resp.status_code == 422
    assert "invalid status" in resp.text


# ---------------------------------------------------------------------------
# GET /api/today/entries
# ---------------------------------------------------------------------------


def test_get_entries_filters_by_kind(client: TestClient) -> None:
    _create(client, kind="todo", title="A todo")
    _create(client, kind="note", title="A note")

    resp = client.get(
        "/api/today/entries",
        params={"start": _TODAY, "end": _TODAY, "kind": "todo", "include_artifacts": "false"},
    )
    assert resp.status_code == 200
    body = resp.json()
    titles = [e["title"] for e in body["entries"]]
    assert titles == ["A todo"]
    assert all(e["kind"] == "todo" for e in body["entries"])


def test_get_entries_filters_by_multiple_tags_all_of(client: TestClient) -> None:
    _create(client, title="only a", tags=["a"])
    _create(client, title="only b", tags=["b"])
    _create(client, title="both a and b", tags=["a", "b"])

    resp = client.get(
        "/api/today/entries",
        params=[
            ("start", _TODAY),
            ("end", _TODAY),
            ("tag", "a"),
            ("tag", "b"),
            ("include_artifacts", "false"),
        ],
    )
    assert resp.status_code == 200
    body = resp.json()
    titles = {e["title"] for e in body["entries"]}
    assert titles == {"both a and b"}


def test_get_entries_q_is_case_insensitive_title_match(client: TestClient) -> None:
    _create(client, title="DPO fundamentals")
    _create(client, title="Something else")

    resp = client.get(
        "/api/today/entries",
        params={"start": _TODAY, "end": _TODAY, "q": "dpo", "include_artifacts": "false"},
    )
    assert resp.status_code == 200
    body = resp.json()
    titles = [e["title"] for e in body["entries"]]
    assert titles == ["DPO fundamentals"]


def test_get_entries_include_artifacts_false_excludes_synthetic(
    client: TestClient, session: Session
) -> None:
    """Directly insert a zettel and assert it does NOT surface when
    include_artifacts=false."""
    from datetime import UTC, datetime

    from alfred.models.zettel import ZettelCard

    _create(client, title="real row")

    card = ZettelCard(title="synthetic zettel", created_at=datetime(2026, 4, 30, 15, 0, tzinfo=UTC))
    session.add(card)
    session.commit()

    resp = client.get(
        "/api/today/entries",
        params={"start": _TODAY, "end": _TODAY, "include_artifacts": "false"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert all(e["is_synthetic"] is False for e in body["entries"])
    titles = [e["title"] for e in body["entries"]]
    assert "synthetic zettel" not in titles
    assert "real row" in titles


# ---------------------------------------------------------------------------
# PATCH /api/today/entries/{id}
# ---------------------------------------------------------------------------


def test_patch_entries_partial_update_returns_updated_row(client: TestClient) -> None:
    created = _create(client, title="Before", priority=1)
    entry_id = created["id"]

    resp = client.patch(
        f"/api/today/entries/{entry_id}",
        json={"title": "After", "status": "doing"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == entry_id
    assert body["title"] == "After"
    assert body["status"] == "doing"
    # untouched
    assert body["priority"] == 1
    assert body["kind"] == "todo"


def test_patch_entries_returns_404_for_unknown_id(client: TestClient) -> None:
    resp = client.patch("/api/today/entries/999999", json={"title": "x"})
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# DELETE /api/today/entries/{id}
# ---------------------------------------------------------------------------


def test_delete_entries_returns_204_on_hit_and_404_on_miss(client: TestClient) -> None:
    created = _create(client, title="dispose me")
    entry_id = created["id"]

    resp_hit = client.delete(f"/api/today/entries/{entry_id}")
    assert resp_hit.status_code == 204

    resp_miss = client.delete(f"/api/today/entries/{entry_id}")
    assert resp_miss.status_code == 404


# ---------------------------------------------------------------------------
# Smoke — date range rejection surfaces as 422 not 500
# ---------------------------------------------------------------------------


def test_get_entries_invalid_date_range_returns_422(client: TestClient) -> None:
    resp = client.get(
        "/api/today/entries",
        params={"start": "2026-05-10", "end": "2026-05-01"},
    )
    assert resp.status_code == 422


def test_entry_date_isoformat_round_trips(client: TestClient) -> None:
    body = _create(client, entry_date=str(date(2026, 5, 1)), title="future day")
    assert body["entry_date"] == "2026-05-01"
