from __future__ import annotations

import logging

from alfred.core import agno_tracing
from alfred.services.web_search import search_web as _service_search_web

from ._tooling import agno_tool as tool

logger = logging.getLogger(__name__)


def render_web_search_markdown(query: str, max_results: int = 10) -> str:
    """Return markdown for a web search using service results.

    Defaults to SearxNG provider for agent/tool calls to avoid public engine
    rate limits. Set `SEARXNG_HOST` (or `SEARX_HOST`) in env to enable.
    """
    try:
        # Prefer SearxNG by default for tools/agents
        k = max(1, int(max_results))
        payload = _service_search_web(q=query, mode="searx", searx_k=k)
        hits = payload.get("hits", [])[: max(0, int(max_results))]
        provider = payload.get("provider", "web")

        if not hits:
            return f"### Web Search (provider: {provider})\n\nNo results for: {query}"

        lines = [f"### Web Search (provider: {provider})", "", f"Query: {query}", ""]
        for i, h in enumerate(hits, start=1):
            title = h.get("title") or h.get("url") or "(untitled)"
            url = h.get("url") or ""
            snippet = (h.get("snippet") or "").strip()
            source = h.get("source")
            source_note = f" — {source}" if source else ""
            lines.append(f"{i}. [{title}]({url}){source_note}")
            if snippet:
                lines.append(f"   - {snippet}")
        result = "\n".join(lines)
        try:
            agno_tracing.log_tool_call(
                name="search_web",
                args={"query": query, "max_results": max_results},
                result={"provider": provider, "hits_count": len(hits)},
            )
        except Exception:
            pass
        return result
    except Exception as exc:  # pragma: no cover - defensive path
        logger.warning("web search failed: %s", exc)
        try:
            agno_tracing.log_tool_call(
                name="search_web",
                args={"query": query, "max_results": max_results},
                result=None,
                error=str(exc),
            )
        except Exception:
            pass
        return (
            "### Web Search\n\n"
            f"⚠️ Unable to complete web search for: {query}.\n\n"
            f"Error: {exc}"
        )


@tool()
def search_web(query: str, max_results: int = 10) -> str:
    """Search the web for recent and relevant results.

    Use this when the user asks to look up information on the public web
    (news, blogs, docs, forum posts). Return a concise summary with links.
    """
    return render_web_search_markdown(query, max_results)
