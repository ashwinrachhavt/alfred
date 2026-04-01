"""Tool registry for the orchestrator agent.

Holds LangChain BaseTool instances and provides lookup/execution.
The registry is the single source of truth for what tools the agent can use.
"""

from __future__ import annotations

import logging
from typing import Any

from langchain_core.tools import BaseTool

logger = logging.getLogger(__name__)


class ToolRegistry:
    """Register, list, and execute tools for the master agent."""

    def __init__(self) -> None:
        self.tools: dict[str, BaseTool] = {}

    def register(self, tool: BaseTool) -> None:
        """Register a LangChain tool. Overwrites if name already exists."""
        self.tools[tool.name] = tool

    def get_lc_tools(self) -> list[BaseTool]:
        """Return all registered tools as a list (for LLM binding)."""
        return list(self.tools.values())

    def execute(self, name: str, args: dict[str, Any]) -> Any:
        """Execute a tool by name. Raises KeyError if not found."""
        if name not in self.tools:
            raise KeyError(f"Tool not registered: {name}")
        return self.tools[name].invoke(args)
