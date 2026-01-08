from __future__ import annotations

from typing import Any, Callable

from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field

from alfred.agents.utils.adapters import structured_tool


class WebSearchInput(BaseModel):
    q: str = Field(..., min_length=1, description="Search query")
    mode: str = Field("searx", description="Provider mode (e.g., searx, auto, ddg)")
    searx_k: int = Field(5, ge=1, le=50, description="Top-k results for SearxNG")
    categories: str | None = Field(None, description="Optional Searx category filter")
    time_range: str | None = Field(None, description="Optional Searx time range")


def make_web_search_tool(*, search_web: Callable[..., dict[str, Any]]) -> BaseTool:
    """Expose Alfred web search as a structured LangChain tool.

    `search_web` is injected to keep this tool adapter independent from the DI layer.
    It must be compatible with `alfred.services.web_service.search_web`.
    """

    def _run(
        q: str,
        mode: str = "searx",
        searx_k: int = 5,
        categories: str | None = None,
        time_range: str | None = None,
    ) -> dict[str, Any]:
        return search_web(
            q=q,
            mode=mode,
            searx_k=searx_k,
            categories=categories,
            time_range=time_range,
        )

    return structured_tool(
        name="web_search",
        description=(
            "Search the public web and return a JSON payload with top hits "
            "(title, url, snippet). Use for up-to-date facts."
        ),
        args_schema=WebSearchInput,
        func=_run,
    )
