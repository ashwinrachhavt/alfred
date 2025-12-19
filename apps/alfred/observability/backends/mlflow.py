from __future__ import annotations

import importlib.util
import json
import logging
import uuid
from datetime import datetime
from typing import Any

from .base import SpanContext, TracingBackend

logger = logging.getLogger(__name__)


class MLflowBackend(TracingBackend):
    """MLflow tracing backend implementation."""

    def __init__(
        self,
        *,
        tracking_uri: str = "http://localhost:5000",
        experiment_name: str = "alfred",
        run_name_prefix: str = "",
    ) -> None:
        """Initialize MLflow backend."""
        self.tracking_uri = tracking_uri
        self.experiment_name = experiment_name
        self.run_name_prefix = run_name_prefix

        if importlib.util.find_spec("mlflow") is None:
            raise ImportError(
                "MLflow is not installed. Install with: pip install mlflow"
            )

        import mlflow  # type: ignore

        self.mlflow = mlflow

        # Set tracking URI
        self.mlflow.set_tracking_uri(tracking_uri)

        # Create or get experiment
        try:
            experiment = self.mlflow.get_experiment_by_name(experiment_name)
            if experiment is None:
                self.experiment_id = self.mlflow.create_experiment(experiment_name)
            else:
                self.experiment_id = experiment.experiment_id
        except Exception as exc:  # noqa: BLE001
            # Fallback to default experiment
            self.experiment_id = "0"
            logger.warning(
                "Could not set MLflow experiment '%s': %s", experiment_name, exc
            )

        # Track active runs and spans
        self._active_runs: dict[str, Any] = {}
        self._active_spans: dict[str, SpanContext] = {}

    def start_trace(
        self,
        name: str,
        *,
        metadata: dict[str, Any] | None = None,
        tags: dict[str, str] | None = None,
        user_id: str | None = None,
    ) -> str:
        """Start a new MLflow run (trace)."""
        trace_id = str(uuid.uuid4())
        run_name = f"{self.run_name_prefix}{name}" if self.run_name_prefix else name

        run = self.mlflow.start_run(
            experiment_id=self.experiment_id,
            run_name=run_name,
            tags={
                "trace_id": trace_id,
                "user_id": user_id or "unknown",
                **(tags or {}),
            },
        )

        self._active_runs[trace_id] = run

        # Log initial metadata
        if metadata:
            with self.mlflow.start_run(run_id=run.info.run_id):
                for key, value in metadata.items():
                    try:
                        self.mlflow.log_param(key, value)
                    except Exception:  # noqa: BLE001
                        # Skip non-serializable values
                        pass

        return trace_id

    def start_span(
        self,
        name: str,
        *,
        trace_id: str | None = None,
        parent_id: str | None = None,
        span_type: str = "function",
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """Start a new span within an MLflow run."""
        span_id = str(uuid.uuid4())

        # Create span context
        span = SpanContext(
            span_id=span_id,
            trace_id=trace_id or "unknown",
            parent_id=parent_id,
            name=name,
            start_time=datetime.now(),
            metadata=metadata or {},
        )

        self._active_spans[span_id] = span

        # Log span start as event
        if trace_id and trace_id in self._active_runs:
            with self.mlflow.start_run(
                run_id=self._active_runs[trace_id].info.run_id
            ):
                self.mlflow.log_param(f"span.{span_id}.name", name)
                self.mlflow.log_param(f"span.{span_id}.type", span_type)
                if metadata:
                    self.mlflow.log_dict(metadata, f"spans/{span_id}_metadata.json")

        return span_id

    def end_span(
        self,
        span_id: str,
        *,
        output: Any | None = None,
        error: Exception | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """End a span and log its results."""
        if span_id not in self._active_spans:
            return

        span = self._active_spans[span_id]
        trace_id = span.trace_id

        # Calculate duration
        duration = (
            (datetime.now() - span.start_time).total_seconds()
            if span.start_time
            else 0.0
        )

        if trace_id in self._active_runs:
            with self.mlflow.start_run(
                run_id=self._active_runs[trace_id].info.run_id
            ):
                # Log duration
                self.mlflow.log_metric(f"span.{span_id}.duration", duration)

                # Log error if present
                if error:
                    self.mlflow.log_param(f"span.{span_id}.error", str(error))
                    self.mlflow.log_param(
                        f"span.{span_id}.error_type", type(error).__name__
                    )

                # Log output
                if output is not None:
                    try:
                        output_str = json.dumps(output, default=str)[:1000]
                        self.mlflow.log_param(f"span.{span_id}.output", output_str)
                    except Exception:  # noqa: BLE001
                        pass

                # Log additional metadata
                if metadata:
                    self.mlflow.log_dict(metadata, f"spans/{span_id}_result.json")

        # Remove from active spans
        del self._active_spans[span_id]

    def end_trace(
        self,
        trace_id: str,
        *,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """End an MLflow run (trace)."""
        if trace_id not in self._active_runs:
            return

        run = self._active_runs[trace_id]

        # Log final metadata
        if metadata:
            with self.mlflow.start_run(run_id=run.info.run_id):
                for key, value in metadata.items():
                    try:
                        # Safely coerce to float if possible, else skip
                        if isinstance(value, (int, float)):
                            self.mlflow.log_metric(key, float(value))
                    except Exception:  # noqa: BLE001
                        pass

        # End the run
        self.mlflow.end_run()

        # Remove from active runs
        del self._active_runs[trace_id]

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
        """Log an event to MLflow."""
        if trace_id and trace_id in self._active_runs:
            with self.mlflow.start_run(
                run_id=self._active_runs[trace_id].info.run_id
            ):
                event_data: dict[str, Any] = {
                    "name": name,
                    "level": level,
                    "message": message,
                    "timestamp": datetime.now().isoformat(),
                }
                if span_id:
                    event_data["span_id"] = span_id
                if metadata:
                    event_data.update(metadata)

                event_id = str(uuid.uuid4())[:8]
                self.mlflow.log_dict(event_data, f"events/{event_id}_{name}.json")

    def update_span(
        self,
        span_id: str,
        *,
        metadata: dict[str, Any] | None = None,
        tags: dict[str, str] | None = None,
    ) -> None:
        """Update span metadata during execution."""
        if span_id not in self._active_spans:
            return

        span = self._active_spans[span_id]
        trace_id = span.trace_id

        if trace_id in self._active_runs:
            with self.mlflow.start_run(
                run_id=self._active_runs[trace_id].info.run_id
            ):
                if metadata:
                    span.metadata = {**(span.metadata or {}), **metadata}
                    self.mlflow.log_dict(
                        span.metadata or {}, f"spans/{span_id}_metadata.json"
                    )

                if tags:
                    for key, value in tags.items():
                        self.mlflow.set_tag(f"span.{span_id}.{key}", value)

    def flush(self) -> None:
        """Flush pending data (MLflow handles this automatically)."""
        for trace_id in list(self._active_runs.keys()):
            try:
                self.end_trace(trace_id)
            except Exception:  # noqa: BLE001
                logger.exception("Failed to end MLflow trace %s", trace_id)

