from __future__ import annotations

import logging

from alfred.services.wikipedia import retrieve_wikipedia

logger = logging.getLogger(__name__)


def render_wiki_lookup_markdown(query: str, top_k: int = 3) -> str:
    """Return markdown for a Wikipedia lookup using service results."""
    try:
        data = retrieve_wikipedia(query=query, top_k_results=max(1, int(top_k)))
        items = data.get("items", [])
        if not items:
            return f"### Wikipedia\n\nNo entries found for: {query}"

        lines: list[str] = ["### Wikipedia", "", f"Query: {query}", ""]
        for i, item in enumerate(items[: max(1, int(top_k))], start=1):
            meta = item.get("metadata") or {}
            title = meta.get("title") or item.get("title") or "(untitled)"
            content = (item.get("content") or "").strip()
            summary = content[:500] + ("…" if len(content) > 500 else "")
            url = meta.get("source") or meta.get("url")
            header = f"{i}. {title}" if not url else f"{i}. [{title}]({url})"
            lines.append(header)
            if summary:
                lines.append(f"   - {summary}")
        result = "\n".join(lines)
        return result
    except Exception as exc:  # pragma: no cover - defensive path
        logger.warning("wikipedia lookup failed: %s", exc)
        return (
            f"### Wikipedia\n\n⚠️ Unable to retrieve Wikipedia results for: {query}.\n\nError: {exc}"
        )


def wiki_lookup(query: str, top_k: int = 3) -> str:
    """Look up encyclopedic context from Wikipedia.

    Use this for definitions, summaries, and background on people, places,
    concepts, and events. Prefer this over web search for general knowledge.
    """
    return render_wiki_lookup_markdown(query, top_k)
