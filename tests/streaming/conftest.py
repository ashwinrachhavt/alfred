"""Shared fixtures for streaming tests — in-memory SQLite session + helpers."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from uuid import UUID

import pytest
import sqlalchemy
from sqlalchemy import JSON, create_engine, event
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel


@pytest.fixture()
def session() -> Iterator[Session]:
    """Ephemeral in-memory SQLite session with all SQLModel tables created.

    SQLite is used for fast unit tests. Tests only verify shape + ordering.
    Postgres-specific index behavior (GIN, partial indexes) is not exercised here.
    """
    from sqlalchemy import String
    from sqlalchemy.dialects import postgresql, sqlite

    # Monkey-patch JSONB and UUID to work with SQLite
    original_visit_JSONB = getattr(sqlite.base.SQLiteTypeCompiler, "visit_JSONB", None)
    original_visit_UUID = getattr(sqlite.base.SQLiteTypeCompiler, "visit_UUID", None)

    def visit_JSONB(self, type_, **kw):
        return self.visit_JSON(JSON(), **kw)

    def visit_UUID(self, type_, **kw):
        return "CHAR(36)"

    sqlite.base.SQLiteTypeCompiler.visit_JSONB = visit_JSONB
    sqlite.base.SQLiteTypeCompiler.visit_UUID = visit_UUID

    try:
        # For SQLite, disable RETURNING to avoid autoincrement issues
        from sqlalchemy import event
        from sqlalchemy.pool import Pool

        engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )

        @event.listens_for(engine, "connect")
        def do_connect(dbapi_conn, connection_record):
            # Disable foreign keys in SQLite for tests (optional)
            dbapi_conn.execute("pragma foreign_keys=ON")

        # SQLModel.metadata.create_all uses the monkeypatched types
        SQLModel.metadata.create_all(engine)

        # Manually fix agent_run_events to use INTEGER PRIMARY KEY for autoincrement
        with engine.begin() as conn:
            # Drop and recreate with proper INTEGER PRIMARY KEY
            conn.execute(sqlalchemy.text("""
                CREATE TABLE IF NOT EXISTS agent_run_events_new (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id CHAR(36) NOT NULL,
                    seq INTEGER NOT NULL,
                    event_type VARCHAR(48) NOT NULL,
                    payload JSON NOT NULL,
                    emitted_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
                    CONSTRAINT uq_run_events_run_seq UNIQUE (run_id, seq),
                    FOREIGN KEY(run_id) REFERENCES agent_runs (id) ON DELETE CASCADE
                )
            """))
            conn.execute(sqlalchemy.text("DROP TABLE IF EXISTS agent_run_events"))
            conn.execute(sqlalchemy.text("ALTER TABLE agent_run_events_new RENAME TO agent_run_events"))

            # Manually fix agent_run_snapshots to use INTEGER PRIMARY KEY for autoincrement
            conn.execute(sqlalchemy.text("""
                CREATE TABLE IF NOT EXISTS agent_run_snapshots_new (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id CHAR(36) NOT NULL,
                    up_to_seq INTEGER NOT NULL,
                    state JSON NOT NULL,
                    message_text TEXT NOT NULL DEFAULT '',
                    thinking_text TEXT NOT NULL DEFAULT '',
                    tokens_so_far INTEGER NOT NULL DEFAULT 0,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
                    CONSTRAINT uq_run_snapshots_run_seq UNIQUE (run_id, up_to_seq),
                    FOREIGN KEY(run_id) REFERENCES agent_runs (id) ON DELETE CASCADE
                )
            """))
            conn.execute(sqlalchemy.text("DROP TABLE IF EXISTS agent_run_snapshots"))
            conn.execute(sqlalchemy.text("ALTER TABLE agent_run_snapshots_new RENAME TO agent_run_snapshots"))

        with Session(engine) as s:
            yield s
    finally:
        # Restore original methods if they existed
        if original_visit_JSONB is None:
            delattr(sqlite.base.SQLiteTypeCompiler, "visit_JSONB")
        else:
            sqlite.base.SQLiteTypeCompiler.visit_JSONB = original_visit_JSONB
        if original_visit_UUID is None:
            delattr(sqlite.base.SQLiteTypeCompiler, "visit_UUID")
        else:
            sqlite.base.SQLiteTypeCompiler.visit_UUID = original_visit_UUID


@pytest.fixture()
def now() -> datetime:
    return datetime(2026, 5, 1, 12, 0, 0, tzinfo=UTC)


@pytest.fixture()
def fixed_run_id() -> UUID:
    return UUID("00000000-0000-4000-8000-000000000001")
