"""Integration tests for reflection + manual-trigger routes (T12).

Covers:
- ``GET /reflections/{date}`` — 404 when missing, 200 + row when present
- ``GET /reflections?start=..&end=..`` — range query, descending order
- ``POST /pipeline/run`` — sync path persists a reflection, async path
  dispatches to Celery via ``.delay(...)``

Uses the same in-memory SQLite + ``StaticPool`` pattern as
``test_entries_routes.py`` so threadpool-backed FastAPI TestClient
requests see the same DB the fixtures seed.
"""

from __future__ import annotations

from collections.abc import Generator
from datetime import UTC, date, datetime
from typing import Any
from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, select

from alfred.api.dependencies import get_db_session
from alfred.api.today.routes import router as today_router
from alfred.models.doc_storage import DocumentRow  # noqa: F401 - metadata
from alfred.models.today import DailyReflectionRow
from alfred.models.zettel import ZettelCard, ZettelReview  # noqa: F401 - metadata

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def session() -> Generator[Session, None, None]:
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


@pytest.fixture(autouse=True)
def _no_redis(monkeypatch: pytest.MonkeyPatch) -> None:
    """Force the task-body redis helper to return None so the lock
    gracefully no-ops during tests."""
    from alfred.tasks import today_pipeline

    monkeypatch.setattr(today_pipeline, "get_redis_client", lambda: None)


@pytest.fixture(autouse=True)
def _session_as_task_session(monkeypatch: pytest.MonkeyPatch, session: Session) -> None:
    """Make the task body's ``get_session`` yield the same in-memory
    SQLite session the route uses — so the sync trigger + assertions run
    against a single DB."""
    from alfred.tasks import today_pipeline

    def _yield_shared_session() -> Generator[Session, None, None]:
        # Do NOT close the session after use — pytest owns its lifecycle
        # via the fixture. A no-op close is handled by yielding a session
        # whose ``.close`` we swallow.
        yield session

    class _NonClosingSession:
        def __init__(self, inner: Session) -> None:
            self._inner = inner

        def __getattr__(self, name: str) -> Any:
            if name == "close":
                return lambda: None
            return getattr(self._inner, name)

    def _fake_get_session() -> Generator[Any, None, None]:
        yield _NonClosingSession(session)

    monkeypatch.setattr(today_pipeline, "get_session", _fake_get_session)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _seed_reflection(
    session: Session,
    *,
    entry_date: date,
    digest_md: str = "- did the thing",
    run_id: str = "abc123abc123",
) -> DailyReflectionRow:
    row = DailyReflectionRow(
        entry_date=entry_date,
        user_id=None,
        digest_md=digest_md,
        stats={"entry_counts": {"todo": 1, "note": 0}},
        pipeline_run_id=run_id,
        stages_ran=["enrich", "connect", "reflect", "prep"],
        generated_at=datetime.now(UTC).replace(tzinfo=None),
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


# ---------------------------------------------------------------------------
# GET /reflections/{entry_date}
# ---------------------------------------------------------------------------


def test_get_reflection_returns_404_when_missing(client: TestClient) -> None:
    resp = client.get("/api/today/reflections/2026-04-29")
    assert resp.status_code == 404
    assert "2026-04-29" in resp.text


def test_get_reflection_returns_row_when_present(client: TestClient, session: Session) -> None:
    _seed_reflection(session, entry_date=date(2026, 4, 29), digest_md="- shipped T12")

    resp = client.get("/api/today/reflections/2026-04-29")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["entry_date"] == "2026-04-29"
    assert body["digest_md"] == "- shipped T12"
    assert body["stages_ran"] == ["enrich", "connect", "reflect", "prep"]
    assert body["pipeline_run_id"] == "abc123abc123"
    assert body["stats"]["entry_counts"]["todo"] == 1


# ---------------------------------------------------------------------------
# GET /reflections?start=..&end=..
# ---------------------------------------------------------------------------


def test_list_reflections_returns_range_descending(client: TestClient, session: Session) -> None:
    _seed_reflection(session, entry_date=date(2026, 4, 27), run_id="r27")
    _seed_reflection(session, entry_date=date(2026, 4, 28), run_id="r28")
    _seed_reflection(session, entry_date=date(2026, 4, 29), run_id="r29")

    resp = client.get(
        "/api/today/reflections",
        params={"start": "2026-04-27", "end": "2026-04-29"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert [r["entry_date"] for r in body] == ["2026-04-29", "2026-04-28", "2026-04-27"]


def test_list_reflections_rejects_out_of_range_window(client: TestClient) -> None:
    resp = client.get(
        "/api/today/reflections",
        params={"start": "2026-01-01", "end": "2026-04-30"},
    )
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# POST /pipeline/run — synchronous
# ---------------------------------------------------------------------------


def test_post_pipeline_run_sync_persists_reflection(client: TestClient, session: Session) -> None:
    """``enqueue=False`` runs the pipeline in-process. DigestAgent
    catches its own LLM exceptions, so even without a live model we get
    an empty digest and a persisted reflection row."""
    resp = client.post(
        "/api/today/pipeline/run",
        json={"entry_date": "2026-04-29", "tz": "UTC", "enqueue": False},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["dispatched"] is False
    assert body["result"] is not None
    assert body["result"]["status"] == "ok"
    assert body["result"]["date"] == "2026-04-29"
    assert body["result"]["stages_ran"] == ["enrich", "connect", "reflect", "prep"]

    # Row was written to the shared session.
    stmt = select(DailyReflectionRow).where(DailyReflectionRow.entry_date == date(2026, 4, 29))
    row = session.exec(stmt).one()
    assert row.pipeline_run_id == body["result"]["run_id"]


# ---------------------------------------------------------------------------
# POST /pipeline/run — enqueue=True dispatches to Celery
# ---------------------------------------------------------------------------


def test_post_pipeline_run_async_calls_delay(client: TestClient) -> None:
    with patch(
        "alfred.tasks.today_pipeline.run_for_date.delay",
    ) as mock_delay:
        mock_delay.return_value.id = "celery-task-xyz"

        resp = client.post(
            "/api/today/pipeline/run",
            json={
                "entry_date": "2026-04-29",
                "tz": "America/Los_Angeles",
                "enqueue": True,
            },
        )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["dispatched"] is True
    assert body["task_id"] == "celery-task-xyz"
    assert body["result"] is None
    mock_delay.assert_called_once_with(
        entry_date="2026-04-29",
        tz_name="America/Los_Angeles",
        user_id=None,
    )
