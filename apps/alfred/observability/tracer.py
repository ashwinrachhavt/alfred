from __future__ import annotations

import logging
import random
from contextlib import contextmanager
from functools import lru_cache
from typing import Any

from .config import ObservabilityConfig, TracingBackend as BackendEnum
from .backends.base import TracingBackend
from .backends.mlflow import MLflowBackend
from .backends.noop import NoOpBackend
from .context import (
    get_current_span,
    get_current_trace,
    set_current_span,
    set_current_trace,
)

logger = logging.getLogger(__name__)


class Tracer:
    """Main tracer interface with backend abstraction."""

    def __init__(self, config: ObservabilityConfig) -> None:
        self.config = config
        self._backend: TracingBackend | None = None

    @property
    def backend(self) -> TracingBackend:
        """Lazy-load backend based on configuration."""
        if self._backend is not None:
            return self._backend

        if not self.config.enabled:
            self._backend = NoOpBackend()
            return self._backend

        try:
            if self.config.backend == BackendEnum.MLFLOW:
                self._backend = MLflowBackend(
                    tracking_uri=self.config.mlflow_tracking_uri,
                    experiment_name=self.config.mlflow_experiment_name,
                    run_name_prefix=self.config.mlflow_run_name_prefix,
                )
            elif self.config.backend == BackendEnum.LANGFUSE:
                # Optional: if implemented later, import here.
                try:
                    from .backends.langfuse import (  # type: ignore
                        LangfuseBackend,
                    )

                    self._backend = LangfuseBackend(
                        public_key=self.config.langfuse_public_key,
                        secret_key=(
                            self.config.langfuse_secret_key.get_secret_value()
                            if self.config.langfuse_secret_key
                            else None
                        ),
                        host=self.config.langfuse_host,
                    )
                except Exception:  # noqa: BLE001
                    logger.warning(
                        "Langfuse backend requested but not available; using NoOp"
                    )
                    self._backend = NoOpBackend()
            else:
                self._backend = NoOpBackend()
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "Failed to initialize tracing backend '%s': %s. Falling back to NoOp.",
                self.config.backend,
                exc,
            )
            self._backend = NoOpBackend()

        return self._backend

    def should_trace(self) -> bool:
        """Check if current request should be traced (sampling)."""
        try:
            return random.random() < float(self.config.sample_rate)
        except Exception:  # noqa: BLE001
            return False

    @contextmanager
    def trace(
        self,
        name: str,
        *,
        metadata: dict[str, Any] | None = None,
        user_id: str | None = None,
    ):
        """Context manager for tracing a complete operation."""
        if not self.should_trace():
            yield None
            return

        trace_id = self.backend.start_trace(name, metadata=metadata, user_id=user_id)
        set_current_trace(trace_id)

        try:
            yield trace_id
        except Exception as exc:  # noqa: BLE001
            self.backend.log_event(
                "trace_error",
                trace_id=trace_id,
                level="ERROR",
                message=str(exc),
                metadata={"error_type": type(exc).__name__},
            )
            raise
        finally:
            try:
                self.backend.end_trace(trace_id, metadata=metadata)
            finally:
                set_current_trace(None)

    @contextmanager
    def span(
        self,
        name: str,
        *,
        span_type: str = "function",
        metadata: dict[str, Any] | None = None,
    ):
        """Context manager for tracing a span within a trace."""
        trace_id = get_current_trace()
        if not trace_id:
            # No active trace, create one implicitly
            with self.trace(name, metadata=metadata):
                yield None
            return

        parent_id = get_current_span()
        span_id = self.backend.start_span(
            name,
            trace_id=trace_id,
            parent_id=parent_id,
            span_type=span_type,
            metadata=metadata,
        )
        set_current_span(span_id)

        error: Exception | None = None
        try:
            yield span_id
        except Exception as exc:  # noqa: BLE001
            error = exc
            raise
        finally:
            try:
                self.backend.end_span(span_id, error=error, metadata=metadata)
            finally:
                set_current_span(parent_id)

    def log_event(
        self,
        name: str,
        *,
        level: str = "INFO",
        message: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Log an event to the current trace/span."""
        trace_id = get_current_trace()
        span_id = get_current_span()

        self.backend.log_event(
            name,
            trace_id=trace_id,
            span_id=span_id,
            level=level,
            message=message,
            metadata=kwargs or None,
        )


@lru_cache
def get_tracer() -> Tracer:
    """Get singleton tracer instance."""
    config = ObservabilityConfig()
    return Tracer(config)

