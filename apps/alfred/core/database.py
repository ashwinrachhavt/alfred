"""Database engine and session helpers (SQLModel-compatible)."""

from __future__ import annotations

import json
from collections.abc import Generator
from datetime import date, datetime

from sqlalchemy import create_engine


def _json_serializer(obj: object) -> str:
    """JSON serializer for SQLAlchemy JSON columns that handles datetime."""

    def _default(o: object) -> str:
        if isinstance(o, datetime | date):
            return o.isoformat()
        raise TypeError(f"Object of type {type(o).__name__} is not JSON serializable")

    return json.dumps(obj, default=_default)
from sqlalchemy.orm import sessionmaker
from sqlmodel import Session

from alfred.core.exceptions import ConfigurationError
from alfred.core.settings import settings


def normalize_db_url(url: str) -> str:
    """Normalize database URL for SQLAlchemy.

    - Force explicit psycopg driver for Postgres URLs
    - Leave other schemes untouched
    """
    if url.startswith("postgres://"):
        return "postgresql+psycopg://" + url[len("postgres://") :]
    if url.startswith("postgresql://") and "+" not in url.split(":", 1)[0]:
        return "postgresql+psycopg://" + url[len("postgresql://") :]
    return url


DB_URL = normalize_db_url(settings.database_url)

try:
    engine_kwargs: dict[str, object] = {
        "future": True,
        "pool_pre_ping": True,
    }

    if DB_URL.startswith("sqlite"):
        # Needed for FastAPI + threadpool usage in dev/test.
        engine_kwargs["connect_args"] = {"check_same_thread": False}

    if DB_URL.startswith("postgresql"):
        engine_kwargs.update(
            pool_size=int(settings.db_pool_size),
            max_overflow=int(settings.db_max_overflow),
            pool_timeout=int(settings.db_pool_timeout),
            pool_recycle=int(settings.db_pool_recycle_seconds),
        )

    engine = create_engine(DB_URL, json_serializer=_json_serializer, **engine_kwargs)
except ModuleNotFoundError as exc:  # pragma: no cover - runtime dependency hint
    if settings.database_url.startswith("postgres"):
        raise ConfigurationError(
            'PostgreSQL driver missing. Run: pip install "psycopg[binary]" '
            "or use SQLite locally: DATABASE_URL=sqlite:///apps/alfred/alfred.db",
        ) from exc
    raise
SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,
    class_=Session,
)


def get_session() -> Generator[Session, None, None]:
    """Yield a SQLAlchemy session scoped to the request lifecycle."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


__all__ = ["engine", "get_session", "SessionLocal", "normalize_db_url"]
