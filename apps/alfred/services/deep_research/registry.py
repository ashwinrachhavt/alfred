"""Tool registry for deep research agents.

Specs reference tools by name; the registry resolves those names to real
`@tool`-decorated callables at agent-build time. This is the security
boundary: a spec cannot reference a tool that is not registered here.

           spec.tool_allowlist = ["search_web", "search_papers"]
                                         │
                                         ▼
                  get_tool_registry().resolve(names)
                                         │
                                         ▼
                  [search_web_tool, search_papers_tool]
                                         │
                                         ▼
                           create_deep_agent(tools=...)
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

from langchain_core.tools import BaseTool

from alfred.agents.tools.research_tools import (
    deep_research as deep_research_tool,
)
from alfred.agents.tools.research_tools import (
    scrape_url,
    search_kb_for_research,
    search_papers,
    search_web,
)
from alfred.schemas.research_agent import ToolCatalogEntry


@dataclass(frozen=True)
class ToolEntry:
    name: str
    tool: BaseTool
    description: str
    requires_connector: str | None = None
    category: str = "general"


class ResearchToolRegistry:
    """Registry of tools available to deep research agents."""

    def __init__(self, entries: list[ToolEntry]) -> None:
        self._by_name: dict[str, ToolEntry] = {e.name: e for e in entries}

    def resolve(self, names: list[str]) -> list[BaseTool]:
        """Return tool callables for the given names. Raises on unknown names."""
        missing = [n for n in names if n not in self._by_name]
        if missing:
            raise ValueError(f"Unknown tool(s): {missing}. Known: {list(self._by_name)}")
        return [self._by_name[n].tool for n in names]

    def catalog(self) -> list[ToolCatalogEntry]:
        """Return the list of available tools for UI population."""
        return [
            ToolCatalogEntry(
                name=e.name,
                description=e.description,
                requires_connector=e.requires_connector,
                category=e.category,
            )
            for e in self._by_name.values()
        ]

    def names(self) -> list[str]:
        return list(self._by_name)


@lru_cache(maxsize=1)
def get_tool_registry() -> ResearchToolRegistry:
    """Singleton registry. Extend here when adding new research tools."""
    return ResearchToolRegistry(
        [
            ToolEntry(
                name="search_web",
                tool=search_web,
                description="Search the web for current information via SearxNG. Returns titles, URLs, snippets.",
                requires_connector="searxng",
                category="search",
            ),
            ToolEntry(
                name="search_papers",
                tool=search_papers,
                description="Search academic papers via arXiv or Semantic Scholar.",
                requires_connector=None,
                category="search",
            ),
            ToolEntry(
                name="search_kb",
                tool=search_kb_for_research,
                description="Search the user's personal knowledge base (zettels).",
                requires_connector=None,
                category="knowledge",
            ),
            ToolEntry(
                name="scrape_url",
                tool=scrape_url,
                description="Fetch and extract full content from a URL via Firecrawl.",
                requires_connector="firecrawl",
                category="scrape",
            ),
            ToolEntry(
                name="deep_research_cached",
                tool=deep_research_tool,
                description="Queue a legacy cached deep-research job (returns task id). Prefer direct tools for new specs.",
                requires_connector=None,
                category="legacy",
            ),
        ]
    )
