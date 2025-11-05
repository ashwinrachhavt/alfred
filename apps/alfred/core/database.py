"""Database helpers for Alfred."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator, Optional

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from alfred.core.config import settings

logger = logging.getLogger(__name__)


class Base(DeclarativeBase):
    """Base class for SQLAlchemy ORM models."""

    pass


_ENGINE: Optional[AsyncEngine] = None
_SESSION_MAKER: Optional[async_sessionmaker[AsyncSession]] = None


def _ensure_engine() -> None:
    """Initialise the async engine & sessionmaker lazily."""

    global _ENGINE, _SESSION_MAKER  # noqa: PLW0603 - module level cache
    if _ENGINE is not None:
        return
    dsn = settings.database_url_async
    if not dsn:
        logger.info("Database URL not configured; Postgres features disabled")
        return
    _ENGINE = create_async_engine(dsn, future=True, echo=False)
    _SESSION_MAKER = async_sessionmaker(_ENGINE, expire_on_commit=False)


def database_enabled() -> bool:
    """Return True when a database connection has been configured."""

    if _ENGINE is None:
        _ensure_engine()
    return _ENGINE is not None


def get_engine() -> AsyncEngine:
    """Expose the lazily constructed engine."""

    if not database_enabled():  # Triggers engine init
        raise RuntimeError("Database engine is not configured")
    assert _ENGINE is not None
    return _ENGINE


def get_session_maker() -> async_sessionmaker[AsyncSession]:
    """Return the cached sessionmaker."""

    if not database_enabled():
        raise RuntimeError("Database sessionmaker is not configured")
    assert _SESSION_MAKER is not None
    return _SESSION_MAKER


def new_session() -> AsyncSession:
    """Instantiate a new AsyncSession."""

    return get_session_maker()()


@asynccontextmanager
async def get_session() -> AsyncIterator[AsyncSession]:
    """Async context manager that yields an AsyncSession."""

    session = new_session()
    try:
        yield session
    finally:
        await session.close()


async def init_db() -> None:
    """Create tables for all imported ORM models."""

    if not database_enabled():
        logger.info("Skipping DB init; database not configured")
        return
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


__all__ = [
    "Base",
    "database_enabled",
    "get_engine",
    "get_session",
    "get_session_maker",
    "init_db",
    "new_session",
]
