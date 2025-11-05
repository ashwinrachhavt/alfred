"""Database engine and session helpers."""

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from alfred.core.config import settings
from alfred.models import Base

engine = create_engine(
    settings.database_url,
    future=True,
    pool_pre_ping=True,
)
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
