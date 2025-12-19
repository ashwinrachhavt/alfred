"""
Lightweight tracing utilities (Langfuse-first, optional MLflow).

This module provides:
- Backwards-compatible Langfuse helpers: lf_observe, lf_update_span, lf_update_trace
- A simple observe() decorator that prefers Langfuse and gracefully falls back
  to MLflow when OBSERVABILITY_BACKEND=mlflow, else a no-op.

No global state that can break app logic; all integrations are optional and
lazy-loaded. If not configured or not installed, decorators are no-ops.
"""

from __future__ import annotations

import importlib.util
import logging
import os
import time
from typing import Any, Callable, Optional

from alfred.core.settings import settings

_client_cache: Any | None = None
_observe_impl: Optional[Callable[..., Callable[..., Any]]] = None

# --- Optional MLflow support (minimal, decorator-scoped runs) ---
_mlflow_ready: bool | None = None
_mlflow = None  # type: ignore[var-annotated]
_mlflow_experiment_id: str | None = None
_mlflow_run_name_prefix: str = ""

logger = logging.getLogger(__name__)


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
    # Import langfuse lazily and only if installed
    if importlib.util.find_spec("langfuse") is None:
        return None
    from langfuse import Langfuse  # type: ignore
    from langfuse import observe as _obs  # type: ignore

    _observe_impl = _obs
    _client_cache = Langfuse(
        public_key=settings.langfuse_public_key,
        secret_key=(
            settings.langfuse_secret_key.get_secret_value()
            if settings.langfuse_secret_key
            else None
        ),
        host=settings.langfuse_host or None,
        debug=settings.langfuse_debug,
    )
    return _client_cache


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


# ------------------
# Minimal MLflow path
# ------------------


def _init_mlflow() -> bool:
    """Initialize MLflow lazily when OBSERVABILITY_BACKEND=mlflow.

    Uses env vars directly to keep this module self-contained:
      - OBSERVABILITY_BACKEND=mlflow (required to opt-in)
      - MLFLOW_TRACKING_URI (default http://localhost:5000)
      - MLFLOW_EXPERIMENT_NAME (default "alfred")
      - MLFLOW_RUN_NAME_PREFIX (optional)
    """
    global _mlflow_ready, _mlflow, _mlflow_experiment_id, _mlflow_run_name_prefix
    if _mlflow_ready is not None:
        return _mlflow_ready

    if os.getenv("OBSERVABILITY_BACKEND", "").lower() != "mlflow":
        _mlflow_ready = False
        return False

    if importlib.util.find_spec("mlflow") is None:
        logger.warning("OBSERVABILITY_BACKEND=mlflow but mlflow not installed; disabling")
        _mlflow_ready = False
        return False

    import mlflow  # type: ignore

    _mlflow = mlflow
    tracking_uri = os.getenv("MLFLOW_TRACKING_URI", "http://localhost:5000")
    experiment_name = os.getenv("MLFLOW_EXPERIMENT_NAME", "alfred")
    _mlflow_run_name_prefix = os.getenv("MLFLOW_RUN_NAME_PREFIX", "")

    try:
        _mlflow.set_tracking_uri(tracking_uri)
        exp = _mlflow.get_experiment_by_name(experiment_name)
        if exp is None:
            _mlflow_experiment_id = _mlflow.create_experiment(experiment_name)
        else:
            _mlflow_experiment_id = exp.experiment_id
        _mlflow_ready = True
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to init MLflow tracking: %s", exc)
        _mlflow_ready = False

    return _mlflow_ready


def _mlflow_observe(name: Optional[str] = None, as_type: Optional[str] = None):
    """Return a decorator that logs a single function call as an MLflow run.

    We keep it intentionally minimal: start a run, record basic tags/params,
    capture duration and errors, then end the run.
    """

    def _decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
        run_name = name or f"{fn.__module__}.{fn.__qualname__}"
        if _mlflow_run_name_prefix:
            run_name_use = f"{_mlflow_run_name_prefix}{run_name}"
        else:
            run_name_use = run_name

        def _sync(*args: Any, **kwargs: Any):
            assert _mlflow is not None  # only called when ready
            start = time.perf_counter()
            with _mlflow.start_run(run_name=run_name_use, experiment_id=_mlflow_experiment_id):
                try:
                    # Basic annotations
                    _mlflow.set_tag("component", "tracing")
                    _mlflow.set_tag("span_type", as_type or "function")
                    _mlflow.log_param("function", fn.__qualname__)
                    _mlflow.log_param("module", fn.__module__)

                    result = fn(*args, **kwargs)

                    duration = time.perf_counter() - start
                    _mlflow.log_metric("duration_seconds", duration)
                    return result
                except Exception as exc:  # noqa: BLE001
                    _mlflow.set_tag("error_type", type(exc).__name__)
                    _mlflow.log_param("error", str(exc))
                    raise

        async def _async(*args: Any, **kwargs: Any):
            assert _mlflow is not None
            start = time.perf_counter()
            with _mlflow.start_run(run_name=run_name_use, experiment_id=_mlflow_experiment_id):
                try:
                    _mlflow.set_tag("component", "tracing")
                    _mlflow.set_tag("span_type", as_type or "function")
                    _mlflow.log_param("function", fn.__qualname__)
                    _mlflow.log_param("module", fn.__module__)

                    result = await fn(*args, **kwargs)

                    duration = time.perf_counter() - start
                    _mlflow.log_metric("duration_seconds", duration)
                    return result
                except Exception as exc:  # noqa: BLE001
                    _mlflow.set_tag("error_type", type(exc).__name__)
                    _mlflow.log_param("error", str(exc))
                    raise

        # choose wrapper type
        import inspect as _inspect

        if _inspect.iscoroutinefunction(fn):
            return _async  # type: ignore[return-value]
        return _sync  # type: ignore[return-value]

    return _decorator


def observe(
    *, name: Optional[str] = None, as_type: Optional[str] = None
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Unified decorator: prefers Langfuse, falls back to MLflow, else no-op.

    - If Langfuse keys are set and SDK is available, returns Langfuse observe.
    - Else if OBSERVABILITY_BACKEND=mlflow and mlflow is available, returns a
      minimal MLflow-based decorator.
    - Else returns a pass-through decorator.
    """
    # Prefer existing Langfuse behavior
    _init_client()
    if _observe_impl is not None:
        return _observe_impl(name=name, as_type=as_type)

    # Try MLflow if explicitly opted in
    if _init_mlflow():
        return _mlflow_observe(name=name, as_type=as_type)

    # Fallback no-op
    def _noop_decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
        return fn

    return _noop_decorator


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
            # If Langfuse is unavailable, attempt a minimal MLflow annotation
            if _init_mlflow() and _mlflow is not None:
                # Only log if there is an active run (i.e., inside @observe)
                if _mlflow.active_run() is not None:  # type: ignore[attr-defined]
                    if metadata:
                        for k, v in metadata.items():
                            try:
                                _mlflow.log_param(f"span_meta.{k}", v)
                            except Exception:
                                pass
                    if input is not None:
                        try:
                            _mlflow.log_param("span.input", str(input)[:1000])
                        except Exception:
                            pass
                    if output is not None:
                        try:
                            _mlflow.log_param("span.output", str(output)[:1000])
                        except Exception:
                            pass
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
            # Minimal MLflow fallback when inside an active run
            if _init_mlflow() and _mlflow is not None:
                if _mlflow.active_run() is not None:  # type: ignore[attr-defined]
                    if name:
                        try:
                            _mlflow.set_tag("trace.name", name)
                        except Exception:
                            pass
                    if user_id:
                        try:
                            _mlflow.set_tag("trace.user_id", user_id)
                        except Exception:
                            pass
                    if session_id:
                        try:
                            _mlflow.set_tag("trace.session_id", session_id)
                        except Exception:
                            pass
                    if tags:
                        try:
                            _mlflow.set_tag("trace.tags", ",".join(tags))
                        except Exception:
                            pass
                    if metadata:
                        for k, v in metadata.items():
                            try:
                                _mlflow.log_param(f"trace_meta.{k}", v)
                            except Exception:
                                pass
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
