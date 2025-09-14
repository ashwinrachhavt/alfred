from __future__ import annotations

import ssl
from collections.abc import AsyncIterator

from fastapi import FastAPI
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from alfred.core.config import settings


def _ssl_connect_args() -> dict:
    if not settings.db_ssl_ca_path:
        return {}
    ctx = ssl.create_default_context(cafile=settings.db_ssl_ca_path)
    ctx.check_hostname = True
    ctx.verify_mode = ssl.CERT_REQUIRED
    return {"ssl": ctx}


def _pgbouncer_connect_args() -> dict:
    return {"prepared_statement_cache_size": 0} if settings.db_use_pgbouncer else {}


_engine_connect_args = {**_ssl_connect_args(), **_pgbouncer_connect_args()}

_engine: AsyncEngine | None = None
_SessionLocal: async_sessionmaker[AsyncSession] | None = None


def _init_engine() -> None:
    global _engine, _SessionLocal
    if _engine is not None and _SessionLocal is not None:
        return
    _engine = create_async_engine(
        settings.database_url,
        pool_pre_ping=True,
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
        connect_args=_engine_connect_args or None,
    )
    _SessionLocal = async_sessionmaker(_engine, class_=AsyncSession, expire_on_commit=False)


async def get_db() -> AsyncIterator[AsyncSession]:
    if _SessionLocal is None:
        _init_engine()
    assert _SessionLocal is not None
    async with _SessionLocal() as session:
        yield session


def attach_lifespan(app: FastAPI) -> None:
    @app.on_event("startup")
    async def _startup() -> None:  # pragma: no cover - minimal warm-up
        _init_engine()
        assert _engine is not None
        async with _engine.begin() as conn:
            await conn.run_sync(lambda _: None)

    @app.on_event("shutdown")
    async def _shutdown() -> None:  # pragma: no cover - dispose on shutdown
        if _engine is not None:
            await _engine.dispose()
