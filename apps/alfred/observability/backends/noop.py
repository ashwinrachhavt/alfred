from __future__ import annotations

from typing import Any

from .base import TracingBackend


class NoOpBackend(TracingBackend):
    """No-op backend when tracing is disabled or unavailable."""

    def start_trace(self, name: str, **_: Any) -> str:  # noqa: ANN003
        return "noop-trace"

    def start_span(self, name: str, **_: Any) -> str:  # noqa: ANN003
        return "noop-span"

    def end_span(self, span_id: str, **_: Any) -> None:  # noqa: ANN003
        return None

    def end_trace(self, trace_id: str, **_: Any) -> None:  # noqa: ANN003
        return None

    def log_event(self, name: str, **_: Any) -> None:  # noqa: ANN003
        return None

    def update_span(self, span_id: str, **_: Any) -> None:  # noqa: ANN003
        return None

    def flush(self) -> None:
        return None

