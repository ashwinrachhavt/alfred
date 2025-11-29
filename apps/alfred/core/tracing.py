"""
Lightweight Langfuse tracing utilities.

This module provides a thin wrapper around the Langfuse Python SDK so the
rest of the codebase can annotate functions with a decorator without
introducing a hard dependency. If Langfuse is not configured or not
installed, the decorator becomes a no-op.
"""

from __future__ import annotations

from typing import Any, Callable, Optional

from .config import settings

_client_cache: Any | None = None
_observe_impl: Optional[Callable[..., Callable[..., Any]]] = None


def _init_client() -> Any | None:
    """Create and cache the Langfuse client if configured, else return None.

    Uses env-driven settings: LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY, LANGFUSE_HOST.
    """
    global _client_cache, _observe_impl
    if _client_cache is not None or not settings.langfuse_tracing_enabled:
        return _client_cache

    # Only initialize when keys are present
    if not (settings.langfuse_public_key and settings.langfuse_secret_key):
        return None
    try:
        from langfuse import Langfuse  # type: ignore
        from langfuse import observe as _obs

        _observe_impl = _obs
        _client_cache = Langfuse(
            public_key=settings.langfuse_public_key,
            secret_key=settings.langfuse_secret_key,
            host=settings.langfuse_host or None,
            debug=settings.langfuse_debug,
        )
        return _client_cache
    except Exception:
        # Silently degrade if SDK missing or misconfigured
        _client_cache = None
        _observe_impl = None
        return None


def lf_get_client() -> Any | None:
    """Return the Langfuse client or None if unavailable."""
    return _init_client()


def lf_observe(
    *, name: Optional[str] = None, as_type: Optional[str] = None
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Decorator factory. If Langfuse is configured, returns @observe(...).

    Otherwise, returns a pass-through decorator.
    """

    _init_client()

    if _observe_impl is None:
        # No-op decorator
        def _noop_decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
            return fn

        return _noop_decorator

    # Langfuse observe decorator
    return _observe_impl(name=name, as_type=as_type)


def lf_update_span(
    *,
    input: Any | None = None,
    output: Any | None = None,
    metadata: dict | None = None,
    level: str | None = None,
    version: str | None = None,
) -> None:
    """Best-effort update of the current span. No-ops if client unavailable."""
    try:
        client = lf_get_client()
        if not client:
            return
        client.update_current_span(
            input=input,  # type: ignore[arg-type]
            output=output,  # type: ignore[arg-type]
            metadata=metadata,
            level=level,
            version=version,
        )
    except Exception:
        # Never let tracing break application logic
        return


def lf_update_trace(
    *,
    name: Optional[str] = None,
    user_id: Optional[str] = None,
    session_id: Optional[str] = None,
    tags: list[str] | None = None,
    public: Optional[bool] = None,
    metadata: dict | None = None,
) -> None:
    """Best-effort update of the current trace. No-ops if client unavailable."""
    try:
        client = lf_get_client()
        if not client:
            return
        client.update_current_trace(
            name=name,
            user_id=user_id,
            session_id=session_id,
            tags=tags,
            public=public,
            metadata=metadata,
        )
    except Exception:
        return
