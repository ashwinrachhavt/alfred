from __future__ import annotations

import contextvars
from typing import Optional

# Thread-safe context variables for async code paths
_current_trace: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "current_trace", default=None
)
_current_span: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "current_span", default=None
)


def get_current_trace() -> Optional[str]:
    """Get the current trace ID."""
    return _current_trace.get()


def set_current_trace(trace_id: Optional[str]) -> None:
    """Set the current trace ID."""
    _current_trace.set(trace_id)


def get_current_span() -> Optional[str]:
    """Get the current span ID."""
    return _current_span.get()


def set_current_span(span_id: Optional[str]) -> None:
    """Set the current span ID."""
    _current_span.set(span_id)

