"""Lazy loaders for CopilotKit integrations."""

from __future__ import annotations

import logging
from functools import lru_cache
from importlib import import_module
from typing import Any, Optional


class CopilotKitUnavailable(RuntimeError):
    """Raised when CopilotKit or its langgraph dependencies are missing."""


@lru_cache(maxsize=1)
def load_remote_endpoint_classes() -> tuple[type, type]:
    """Load the CopilotKit classes needed for remote endpoints.

    Returns:
        A tuple of (CopilotKitRemoteEndpoint, LangGraphAgent).
    """

    try:
        module = import_module("copilotkit")
    except ModuleNotFoundError as exc:  # pragma: no cover - depends on optional install
        missing = exc.name or "copilotkit"
        if missing != "copilotkit":
            hint = (
                "CopilotKit dependency '{missing}' is missing. "
                "Install CopilotKit with its langgraph extras: `pip install copilotkit[langgraph]`."
            ).format(missing=missing)
        else:
            hint = "CopilotKit is not installed. Install it via `pip install copilotkit`."
        raise CopilotKitUnavailable(hint) from exc

    try:
        endpoint_cls = getattr(module, "CopilotKitRemoteEndpoint")
        agent_cls = getattr(module, "LangGraphAgent")
    except AttributeError as exc:  # pragma: no cover - version mismatch
        raise CopilotKitUnavailable(
            "CopilotKit installation missing expected classes. Ensure you are on a supported version."
        ) from exc

    return endpoint_cls, agent_cls


@lru_cache(maxsize=1)
def load_fastapi_endpoint() -> Optional[Any]:
    """Return the optional FastAPI helper from CopilotKit if available."""

    try:
        integrations = import_module("copilotkit.integrations.fastapi")
    except ModuleNotFoundError:  # pragma: no cover - optional aux dependency
        logging.getLogger(__name__).info(
            "CopilotKit FastAPI integration unavailable; skipping remote endpoint wiring."
        )
        return None

    return getattr(integrations, "add_fastapi_endpoint", None)


__all__ = [
    "CopilotKitUnavailable",
    "load_remote_endpoint_classes",
    "load_fastapi_endpoint",
]
