"""Web feature service implementation.

This is the canonical module for the "web" feature.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from alfred.core.tracing import lf_update_span, observe


@observe(name="web_search", as_type="tool")
def search_web(
    q: str,
    *,
    searx_k: int = 10,
    categories: str | None = None,
    time_range: str | None = None,
) -> dict[str, Any]:
    from alfred.core.dependencies import get_primary_web_search_connector

    conn = get_primary_web_search_connector()
    resp = conn.search(q, num_results=searx_k, categories=categories, time_range=time_range)
    payload = {
        "provider": resp.provider,
        "query": resp.query,
        "meta": resp.meta,
        "hits": [
            {"title": h.title, "url": h.url, "snippet": h.snippet, "source": h.source}
            for h in resp.hits
        ],
    }
    # Best-effort span update with input/output metadata (safe: lf_update_span no-ops on failure).
    lf_update_span(
        input={
            "q": q,
            "searx_k": searx_k,
        },
        output={"hits_count": len(resp.hits), "provider": resp.provider},
        metadata={"web_search": True},
    )
    return payload


@dataclass(frozen=True, slots=True)
class WebService:
    """High-level wrapper around Alfred's web search capability."""

    searx_k: int = 10

    def search(self, query: str, **kwargs: Any) -> dict[str, Any]:
        query = (query or "").strip()
        if not query:
            raise ValueError("query must be non-empty")
        return search_web(query, searx_k=self.searx_k, **kwargs)


__all__ = ["WebService", "search_web"]
