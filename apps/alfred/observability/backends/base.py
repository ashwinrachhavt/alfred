from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional


@dataclass
class SpanContext:
    """Context for a single span/trace."""

    span_id: str
    trace_id: str
    parent_id: Optional[str] = None
    name: str = ""
    start_time: datetime | None = None
    metadata: dict[str, Any] | None = None


class TracingBackend(ABC):
    """Abstract base class for tracing backends."""

    @abstractmethod
    def start_trace(
        self,
        name: str,
        *,
        metadata: dict[str, Any] | None = None,
        tags: dict[str, str] | None = None,
        user_id: str | None = None,
    ) -> str:
        """
        Start a new trace.

        Returns:
            trace_id: Unique identifier for the trace
        """

    @abstractmethod
    def start_span(
        self,
        name: str,
        *,
        trace_id: str | None = None,
        parent_id: str | None = None,
        span_type: str = "function",
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """
        Start a new span within a trace.

        Returns:
            span_id: Unique identifier for the span
        """

    @abstractmethod
    def end_span(
        self,
        span_id: str,
        *,
        output: Any | None = None,
        error: Exception | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """End a span and record its output/error."""

    @abstractmethod
    def end_trace(
        self,
        trace_id: str,
        *,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """End a trace."""

    @abstractmethod
    def log_event(
        self,
        name: str,
        *,
        trace_id: str | None = None,
        span_id: str | None = None,
        level: str = "INFO",
        message: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Log an event within a trace/span."""

    @abstractmethod
    def update_span(
        self,
        span_id: str,
        *,
        metadata: dict[str, Any] | None = None,
        tags: dict[str, str] | None = None,
    ) -> None:
        """Update span metadata during execution."""

    @abstractmethod
    def flush(self) -> None:
        """Flush any pending traces/spans."""

