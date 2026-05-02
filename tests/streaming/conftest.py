"""Shared fixtures for streaming tests — in-memory SQLite session + helpers."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from uuid import UUID

import pytest
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel


@pytest.fixture()
def session() -> Iterator[Session]:
    """Ephemeral in-memory SQLite session with all SQLModel tables created.

    SQLite is used for fast unit tests. Tests only verify shape + ordering.
    Postgres-specific index behavior (GIN, partial indexes) is not exercised here.
    """
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


@pytest.fixture()
def now() -> datetime:
    return datetime(2026, 5, 1, 12, 0, 0, tzinfo=UTC)


@pytest.fixture()
def fixed_run_id() -> UUID:
    return UUID("00000000-0000-4000-8000-000000000001")
