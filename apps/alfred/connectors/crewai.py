"""Wrappers for CrewAI and related optional tooling."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from importlib import import_module
from typing import Any, Optional, Tuple, Type


class CrewAIUnavailable(RuntimeError):
    """Raised when the core ``crewai`` dependency is missing."""


@dataclass(frozen=True)
class CrewTools:
    """Container for optional crewai_tools integrations."""

    default_tools: Tuple[Any, ...]
    web_scrape_tool: Optional[Any]
    search_tool: Optional[Any]
    website_search_tool_cls: Optional[Type[Any]]


@lru_cache(maxsize=1)
def load_crewai_classes() -> Tuple[type, type, type, type]:
    """Load core CrewAI classes, raising a friendly error if unavailable."""

    try:
        module = import_module("crewai")
    except ModuleNotFoundError as exc:  # pragma: no cover - depends on optional install
        raise CrewAIUnavailable(
            "CrewAI is not installed. Install it with `pip install crewai` to use Crew workflows."
        ) from exc

    return module.Agent, module.Crew, module.Process, module.Task


@lru_cache(maxsize=1)
def load_crewai_tools() -> CrewTools:
    """Return instantiated optional tools from ``crewai_tools`` when present."""

    try:
        tools_module = import_module("crewai_tools")
    except ModuleNotFoundError:  # pragma: no cover - optional dependency
        return CrewTools(default_tools=tuple(), web_scrape_tool=None, search_tool=None, website_search_tool_cls=None)

    default_tools = []
    search_tool = None
    web_scrape_tool = None

    try:
        scrape_cls = getattr(tools_module, "ScrapeWebsiteTool", None)
        if callable(scrape_cls):
            web_scrape_tool = scrape_cls()
            default_tools.append(web_scrape_tool)
    except Exception:  # pragma: no cover - optional dependency failures
        web_scrape_tool = None

    try:
        search_cls = getattr(tools_module, "SerperDevTool", None)
        if callable(search_cls):
            search_tool = search_cls()
            default_tools.append(search_tool)
    except Exception:  # pragma: no cover - optional dependency failures
        search_tool = None

    website_search_tool_cls: Optional[Type[Any]]
    website_search_tool_cls = getattr(tools_module, "WebsiteSearchTool", None)
    if not callable(website_search_tool_cls):  # type: ignore[assignment]
        website_search_tool_cls = None

    return CrewTools(
        default_tools=tuple(default_tools),
        web_scrape_tool=web_scrape_tool,
        search_tool=search_tool,
        website_search_tool_cls=website_search_tool_cls,
    )


__all__ = [
    "CrewAIUnavailable",
    "CrewTools",
    "load_crewai_classes",
    "load_crewai_tools",
]
