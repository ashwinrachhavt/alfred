"""Web feature service implementation.

This is the canonical module for the "web" feature.
"""

from __future__ import annotations

from dataclasses import dataclass

from alfred.core.tracing import lf_update_span, observe


@observe(name="web_search", as_type="tool")
def search_web(
    q: str,
    mode: str = "searx",
    *,
    brave_pages: int = 10,
    ddg_max_results: int = 50,
    exa_num_results: int = 100,
    tavily_max_results: int = 20,
    tavily_topic: str = "general",
    you_num_results: int = 20,
    searx_k: int = 10,
) -> dict:
    # SearxNG-only: use the process-scoped connector from dependencies.
    from alfred.core.dependencies import get_primary_web_search_connector

    conn = get_primary_web_search_connector()
    resp = conn.search(q)
    payload = {
        "provider": resp.provider,
        "query": resp.query,
        "meta": resp.meta,
        "hits": [
            {"title": h.title, "url": h.url, "snippet": h.snippet, "source": h.source}
            for h in resp.hits
        ],
    }
    # Best-effort span update with input/output metadata
    try:
        lf_update_span(
            input={
                "q": q,
                "mode": "searx",
                "searx_k": searx_k,
            },
            output={"hits_count": len(resp.hits), "provider": resp.provider},
            metadata={"web_search": True},
        )
    except Exception:
        pass
    return payload


@dataclass(frozen=True, slots=True)
class WebService:
    """High-level wrapper around Alfred's web search capability."""

    mode: str = "searx"
    searx_k: int = 10

    def search(self, query: str, **kwargs):
        query = (query or "").strip()
        if not query:
            raise ValueError("query must be non-empty")
        return search_web(query, mode=self.mode, searx_k=self.searx_k, **kwargs)


__all__ = ["WebService", "search_web"]
