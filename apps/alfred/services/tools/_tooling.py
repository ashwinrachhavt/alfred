"""Shared utilities for Agno tools.

Exports `agno_tool`, a decorator compatible with Agno's `@tool`. If Agno is
not installed, it gracefully degrades to a no-op decorator so that importing
tool modules does not crash in environments without Agno.
"""

from __future__ import annotations

from typing import Any, Callable

try:  # Prefer real Agno decorator when available
    from agno.tools import tool as agno_tool  # type: ignore
except Exception:  # pragma: no cover - import fallback

    def agno_tool(*args: Any, **kwargs: Any):  # type: ignore
        def _wrap(func: Callable[..., Any]) -> Callable[..., Any]:
            return func

        # Support bare @agno_tool and @agno_tool(...)
        if args and callable(args[0]) and not kwargs:
            return _wrap(args[0])
        return _wrap
