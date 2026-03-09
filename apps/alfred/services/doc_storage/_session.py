"""Shared session-scope context manager used by all mixins."""

from __future__ import annotations

from contextlib import contextmanager

from sqlmodel import Session

from alfred.core.database import SessionLocal


@contextmanager
def _session_scope(session: Session | None = None):
    if session is not None:
        yield session
    else:
        with SessionLocal() as s:
            yield s
