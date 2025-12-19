"""Shared API dependencies."""

from collections.abc import Generator

from sqlmodel import Session

from alfred.core.database import get_session


def get_db_session() -> Generator[Session, None, None]:
    """Provide a database session for request handlers."""
    yield from get_session()


__all__ = ["get_db_session"]
