"""Agno agent tracing initialization and helpers (MLflow-first).

This module enables lightweight observability for Agno agents using MLflow.
It is safe to import even when MLflow is not installed or not configured.

Environment variables:
  - MLFLOW_TRACKING_URI: e.g., file:///tmp/mlruns or http://localhost:5000
  - MLFLOW_EXPERIMENT_NAME: experiment to use (default: Alfred-Agno)

Usage:
  from alfred.core import agno_tracing
  agno_tracing.init()  # call before creating agents

  with agno_tracing.agent_run("ResearchAgent", {"q": "..."}):
      ... create Agent and run ...
      agno_tracing.log_output({"summary": "..."})

Tools and knowledge services can log spans via log_tool_call(...) and
log_knowledge_event(...). These are no-ops when tracing is disabled.
"""

from __future__ import annotations

import logging
import os
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, Generator, Optional

try:  # optional helper to load .env files lazily
    from dotenv import load_dotenv  # type: ignore
except Exception:  # pragma: no cover - fallback when dotenv missing
    load_dotenv = None  # type: ignore

logger = logging.getLogger(__name__)

_mlflow: Any | None = None
_active: bool = False
_current_agent: Optional[str] = None
_env_loaded: bool = False


def _load_env_files() -> None:
    """Load env from apps/alfred/.env then repo root .env (non-overriding)."""
    global _env_loaded
    if _env_loaded:
        return
    if load_dotenv is None:
        _env_loaded = True
        return
    try:
        here = Path(__file__).resolve()
        app_env = here.parents[1] / ".env"  # apps/alfred/.env
        repo_env = here.parents[3] / ".env"  # repo root .env
        if app_env.exists():
            load_dotenv(dotenv_path=str(app_env), override=False)
        if repo_env.exists():
            load_dotenv(dotenv_path=str(repo_env), override=False)
    except Exception:
        pass
    finally:
        _env_loaded = True


def _load_mlflow() -> Any | None:
    global _mlflow
    if _mlflow is not None:
        return _mlflow
    try:
        import mlflow  # type: ignore

        _mlflow = mlflow
        return mlflow
    except Exception:
        _mlflow = None
        return None


def is_enabled() -> bool:
    """Return True if MLflow tracing is active."""
    return _active and _mlflow is not None


def init() -> bool:
    """Initialize MLflow from environment. Returns True if enabled.

    Safe to call multiple times. Does nothing if MLFLOW_TRACKING_URI is not set
    or MLflow is not installed.
    """
    global _active
    if is_enabled():
        return True

    # Rely on environment as-is; do not auto-load .env here. Tests expect
    # disabled tracing when MLFLOW_TRACKING_URI is not present.

    mlflow = _load_mlflow()
    if mlflow is None:
        logger.debug("MLflow not installed; Agno tracing disabled")
        _active = False
        return False

    uri = os.getenv("MLFLOW_TRACKING_URI")
    if not uri:
        logger.debug("MLFLOW_TRACKING_URI not set; Agno tracing disabled")
        _active = False
        return False

    try:
        # Ensure local file store exists when using file:// scheme
        if uri.startswith("file://"):
            from urllib.parse import urlsplit

            p = urlsplit(uri).path
            try:
                Path(p).mkdir(parents=True, exist_ok=True)
            except Exception:
                pass

        mlflow.set_tracking_uri(uri)
        exp_name = os.getenv("MLFLOW_EXPERIMENT_NAME", "Alfred-Agno")
        mlflow.set_experiment(exp_name)
        _active = True
        logger.info("Agno tracing initialized with MLflow experiment '%s'", exp_name)
        return True
    except Exception as exc:
        logger.warning("Failed to initialize MLflow tracing: %s", exc)
        _active = False
        return False


@contextmanager
def agent_run(agent_name: str, inputs: Dict[str, Any] | None = None) -> Generator[None, None, None]:
    """Context manager to record a single agent invocation as a root run."""
    global _current_agent
    mlflow = _load_mlflow()
    if not is_enabled() or mlflow is None:
        yield
        return

    run = None
    try:
        run = mlflow.start_run(run_name=agent_name)
        _current_agent = agent_name
        if inputs is not None:
            try:
                mlflow.log_dict(inputs, "inputs.json")
            except Exception:
                pass
        mlflow.log_param("agent_name", agent_name)
        yield
    finally:
        _current_agent = None
        try:
            if run is not None:
                mlflow.end_run()
        except Exception:
            pass


def log_output(output: Any) -> None:
    """Log the final agent output as an artifact."""
    mlflow = _load_mlflow()
    if not is_enabled() or mlflow is None:
        return
    try:
        mlflow.log_dict({"output": output}, "output.json")
    except Exception:
        return


def log_tool_call(
    name: str,
    args: Dict[str, Any] | None = None,
    result: Any | None = None,
    error: str | None = None,
) -> None:
    """Record a tool call as a nested run with inputs/outputs."""
    mlflow = _load_mlflow()
    if not is_enabled() or mlflow is None:
        return
    try:
        with mlflow.start_run(run_name=f"tool:{name}", nested=True):
            if _current_agent:
                mlflow.set_tags({"agent": _current_agent, "type": "tool"})
            if args is not None:
                mlflow.log_dict(args, "args.json")
            if result is not None:
                mlflow.log_dict({"result": result}, "result.json")
            if error:
                mlflow.log_param("error", error)
    except Exception:
        return


def log_knowledge_event(op: str, details: Dict[str, Any] | None = None) -> None:
    """Record a knowledge store event (e.g., retrieval) as nested run."""
    mlflow = _load_mlflow()
    if not is_enabled() or mlflow is None:
        return
    try:
        with mlflow.start_run(run_name=f"knowledge:{op}", nested=True):
            if _current_agent:
                mlflow.set_tags({"agent": _current_agent, "type": "knowledge"})
            if details is not None:
                mlflow.log_dict(details, "details.json")
    except Exception:
        return
