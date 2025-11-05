"""Helpers for configuring LangGraph persistence."""

from __future__ import annotations

import logging
from functools import lru_cache
from typing import Any, Optional

from alfred.core.config import settings
from alfred.core.database import database_enabled

logger = logging.getLogger(__name__)

try:  # pragma: no cover - optional dependency
    from langgraph.checkpoint.postgres import PostgresSaver  # type: ignore
except Exception:  # pragma: no cover
    PostgresSaver = None  # type: ignore

try:  # pragma: no cover - optional dependency
    from langgraph.store.postgres import PostgresStore  # type: ignore
except Exception:  # pragma: no cover
    PostgresStore = None  # type: ignore

try:  # fall back to in-memory when Postgres is unavailable
    from langgraph.checkpoint.memory import MemorySaver
except Exception:  # pragma: no cover
    MemorySaver = None  # type: ignore


def _postgres_uri() -> Optional[str]:
    uri = settings.database_url_sync
    if not uri:
        return None
    if not uri.startswith("postgresql"):
        logger.warning("Unsupported database URI for LangGraph: %s", uri)
    return uri


def _build_from_factory(cls: Any, uri: str):
    for method_name in ("from_conn_string", "from_connection_string", "from_uri", "from_url"):
        factory = getattr(cls, method_name, None)
        if callable(factory):
            return factory(uri)
    try:
        return cls(uri)  # type: ignore[call-arg]
    except Exception as exc:  # pragma: no cover
        logger.error("Failed to instantiate %s with URI %s: %s", cls, uri, exc)
        raise


@lru_cache(maxsize=1)
def get_checkpointer():
    """Return a LangGraph checkpointer, preferring Postgres when available."""

    uri = _postgres_uri()
    if uri and PostgresSaver is not None:
        try:
            return _build_from_factory(PostgresSaver, uri)
        except Exception as exc:  # pragma: no cover - fall back to memory
            logger.warning("Falling back to MemorySaver after PostgresSaver failure: %s", exc)
    if MemorySaver is None:
        raise RuntimeError("LangGraph memory saver is unavailable")
    return MemorySaver()


@lru_cache(maxsize=1)
def get_store():
    """Return a LangGraph store backed by Postgres when possible."""

    uri = _postgres_uri()
    if uri and PostgresStore is not None:
        try:
            return _build_from_factory(PostgresStore, uri)
        except Exception as exc:  # pragma: no cover
            logger.warning("LangGraph PostgresStore unavailable: %s", exc)
    if not database_enabled():
        return None
    return None


__all__ = ["get_checkpointer", "get_store"]
