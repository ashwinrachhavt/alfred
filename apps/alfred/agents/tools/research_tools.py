"""Research agent tools -- deep research, web search, and paper search.

Tools for conducting comprehensive research using web search, academic papers,
and knowledge base queries. Includes URL scraping and research orchestration.
"""

from __future__ import annotations

import json
import logging

from langchain_core.tools import tool

from alfred.core.celery_client import BrokerUnavailableError, dispatch_task

logger = logging.getLogger(__name__)


@tool
def deep_research(topic: str, refresh: bool = False) -> str:
    """Queue a comprehensive deep research task. Returns task ID for tracking."""
    try:
        result = dispatch_task(
            "alfred.tasks.deep_research.generate",
            kwargs={"topic": topic, "refresh": refresh},
        )
        return json.dumps({
            "ok": True,
            "topic": topic,
            "task_id": result.id,
            "status": "queued",
            "message": f"Deep research queued for: {topic}",
        })
    except BrokerUnavailableError as exc:
        logger.warning("deep_research unavailable for %s: %s", topic, exc)
        return json.dumps({"error": "Background worker unavailable"})
    except Exception as exc:
        logger.error("deep_research failed: %s", exc)
        return json.dumps({"error": str(exc)})


@tool
def search_web(query: str, max_results: int = 10) -> str:
    """Search the web for current information. Returns titles, URLs, and snippets."""
    try:
        from alfred.connectors.web_connector import WebConnector

        conn = WebConnector(searx_k=max_results)
        response = conn.search(query=query, num_results=max_results)
        output = [
            {
                "title": h.title,
                "url": h.url,
                "snippet": (h.snippet or "")[:300],
                "source": h.source,
            }
            for h in (response.hits or [])[:max_results]
        ]
        return json.dumps(output)
    except Exception as exc:
        logger.warning("search_web failed: %s", exc)
        return json.dumps({"error": str(exc)})


@tool
def search_papers(query: str, source: str = "arxiv", max_results: int = 5) -> str:
    """Search academic papers. Source: arxiv or semantic_scholar. Returns papers with abstracts."""

    def _stringify(val):
        """Convert non-JSON-serializable values (date, datetime) to ISO strings."""
        if hasattr(val, "isoformat"):
            return val.isoformat()
        return val

    try:
        if source == "arxiv":
            from alfred.connectors.arxiv_connector import ArxivConnector

            conn = ArxivConnector()
            docs = conn.search(query=query, max_results=max_results)
            output = [
                {
                    "title": doc.metadata.get("Title"),
                    "authors": doc.metadata.get("Authors"),
                    "abstract": (doc.metadata.get("Summary") or "")[:400],
                    "published": _stringify(doc.metadata.get("Published")),
                    "url": doc.metadata.get("entry_id"),
                    "source": "arxiv",
                }
                for doc in docs
            ]
        elif source == "semantic_scholar":
            from alfred.connectors.semantic_scholar_connector import SemanticScholarClient

            client = SemanticScholarClient()
            papers = client.search_by_keyword(keyword=query, limit=max_results)
            output = [
                {
                    "title": p.get("title"),
                    "authors": [a.get("name") for a in p.get("authors", [])],
                    "abstract": p.get("abstract", "")[:400] if p.get("abstract") else "",
                    "year": p.get("year"),
                    "citation_count": p.get("citationCount", 0),
                    "url": f"https://www.semanticscholar.org/paper/{p.get('paperId')}",
                    "source": "semantic_scholar",
                }
                for p in papers[:max_results]
            ]
        else:
            return json.dumps({"error": f"Unknown source: {source}. Use 'arxiv' or 'semantic_scholar'"})

        return json.dumps(output)
    except Exception as exc:
        logger.warning("search_papers failed: %s", exc)
        return json.dumps({"error": str(exc)})


@tool
def search_kb_for_research(query: str, topic: str | None = None, limit: int = 20) -> str:
    """Search the knowledge base for relevant zettels to inform research. Returns cards with content."""
    try:
        from alfred.core.database import SessionLocal
        from alfred.services.zettelkasten_service import ZettelkastenService

        session = SessionLocal()
        svc = ZettelkastenService(session=session)

        cards = svc.list_cards(q=query, topic=topic, limit=limit)
        output = [
            {
                "id": c.id,
                "title": c.title,
                "topic": c.topic,
                "tags": c.tags,
                "content": (c.content or c.summary or "")[:500],
                "importance": c.importance,
            }
            for c in cards
        ]
        return json.dumps(output)
    except Exception as exc:
        logger.error("search_kb_for_research failed: %s", exc)
        return json.dumps({"error": str(exc)})


@tool
def scrape_url(url: str, render_js: bool = False) -> str:
    """Scrape content from a URL using Firecrawl. Returns title, text, and markdown."""
    try:
        from alfred.connectors.firecrawl_connector import FirecrawlClient
        from alfred.core.settings import settings

        base_url = settings.firecrawl_base_url or "http://localhost:3002/v1"
        client = FirecrawlClient(base_url=base_url)
        response = client.scrape(url=url, render_js=render_js)

        if not response.success:
            return json.dumps({
                "error": "Failed to scrape URL",
                "message": str(response.error or "Unknown error"),
            })

        data = response.data if isinstance(response.data, dict) else {}
        markdown = response.markdown or data.get("markdown") or ""
        content = data.get("content") or markdown
        return json.dumps({
            "ok": True,
            "url": url,
            "title": data.get("title") or data.get("metadata", {}).get("title", ""),
            "content": (content or "")[:2000],
            "markdown": (markdown or "")[:2000],
            "metadata": {
                "author": data.get("author") or data.get("metadata", {}).get("author"),
                "description": data.get("description") or data.get("metadata", {}).get("description"),
                "language": data.get("language") or data.get("metadata", {}).get("language"),
            },
        })
    except Exception as exc:
        logger.warning("scrape_url failed: %s", exc)
        return json.dumps({"error": str(exc), "hint": "Check firecrawl_base_url + FIRECRAWL_API_KEY"})


# List of all research tools for agent registration
RESEARCH_TOOLS = [
    deep_research,
    search_web,
    search_papers,
    search_kb_for_research,
    scrape_url,
]
