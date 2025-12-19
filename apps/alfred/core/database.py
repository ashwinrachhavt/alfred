"""Database engine and session helpers."""

import logging
from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from alfred.core.settings import settings
from alfred.models import Base

logger = logging.getLogger(__name__)


def _with_psycopg(url: str) -> str:
    """Force explicit psycopg driver for Postgres URLs (simple and reliable)."""
    if url.startswith("postgres://"):
        return "postgresql+psycopg://" + url[len("postgres://") :]
    if url.startswith("postgresql://") and "+" not in url.split(":", 1)[0]:
        return "postgresql+psycopg://" + url[len("postgresql://") :]
    return url


DB_URL = _with_psycopg(settings.database_url)

try:
    engine = create_engine(
        DB_URL,
        future=True,
        pool_pre_ping=True,
    )
except ModuleNotFoundError as exc:  # pragma: no cover - runtime dependency hint
    if settings.database_url.startswith("postgres"):
        raise RuntimeError(
            'PostgreSQL driver missing. Run: pip install "psycopg[binary]" \n'
            "Or use SQLite locally: DATABASE_URL=sqlite:///apps/alfred/alfred.db"
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


__all__ = ["Base", "engine", "get_session", "SessionLocal"]
