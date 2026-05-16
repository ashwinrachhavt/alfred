"""Connector agent tools -- query external knowledge sources.

Tools for fetching content from Notion, Readwise, arXiv, RSS, web search,
Wikipedia, GitHub, Linear, and Semantic Scholar. All connectors are lazy-imported
to avoid import-time failures when API keys aren't configured.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from dotenv import load_dotenv
from langchain_core.tools import tool

load_dotenv()

logger = logging.getLogger(__name__)


@tool
def query_notion(query: str | None = None, page_size: int = 10) -> str:
    """Fetch pages from Notion workspace. Returns page titles and last-edited timestamps.

    The optional ``query`` filters pages whose title contains the term (case-insensitive)
    after fetching, since the underlying connector lists pages rather than searching.
    """
    try:
        import asyncio

        from alfred.connectors.notion_history import NotionHistoryConnector

        async def _fetch() -> list[dict[str, Any]]:
            async with NotionHistoryConnector(page_size=page_size) as conn:
                # Over-fetch a bit so client-side filtering still produces ~page_size results
                fetch_limit = page_size * 5 if query else page_size
                return await conn.get_all_pages(limit=fetch_limit, include_content=False)

        pages = asyncio.run(_fetch())
        if query:
            q = query.lower()
            pages = [p for p in pages if q in (p.get("title") or "").lower()]

        output = [
            {
                "id": p.get("page_id"),
                "title": p.get("title") or "Untitled",
                "last_edited": p.get("last_edited_time"),
            }
            for p in pages[:page_size]
        ]
        return json.dumps(output)
    except Exception as exc:
        logger.warning("query_notion failed: %s", exc)
        return json.dumps({"error": str(exc), "hint": "Check NOTION_TOKEN is set"})


@tool
def query_readwise(category: str | None = None, limit: int = 10) -> str:
    """Fetch books and highlights from Readwise. Category: books, articles, tweets, podcasts."""
    try:
        from alfred.connectors.readwise_connector import ReadwiseClient

        client = ReadwiseClient()
        books = client.list_books(category=category, page_size=limit)
        output = [
            {
                "id": b.get("id"),
                "title": b.get("title"),
                "author": b.get("author"),
                "category": b.get("category"),
                "num_highlights": b.get("num_highlights", 0),
            }
            for b in books[:limit]
        ]
        return json.dumps(output)
    except Exception as exc:
        logger.warning("query_readwise failed: %s", exc)
        return json.dumps({"error": str(exc), "hint": "Check READWISE_TOKEN is set"})


@tool
def query_arxiv(query: str, max_results: int = 5) -> str:
    """Search arXiv for academic papers. Returns titles, authors, abstracts, and PDF URLs."""
    try:
        from alfred.connectors.arxiv_connector import ArxivConnector

        conn = ArxivConnector()
        docs = conn.search(query=query, max_results=max_results)
        output = [
            {
                "title": doc.metadata.get("Title"),
                "authors": doc.metadata.get("Authors"),
                "summary": doc.metadata.get("Summary", "")[:300],
                "published": doc.metadata.get("Published"),
                "entry_id": doc.metadata.get("entry_id"),
            }
            for doc in docs
        ]
        return json.dumps(output)
    except Exception as exc:
        logger.warning("query_arxiv failed: %s", exc)
        return json.dumps({"error": str(exc)})


@tool
def query_rss(feed_url: str, limit: int = 10) -> str:
    """Fetch entries from an RSS/Atom feed. Returns titles, links, and summaries."""
    try:
        from alfred.connectors.rss_connector import RSSClient

        feed = RSSClient().fetch_feed(feed_url)
        entries = feed.get("entries", []) if isinstance(feed, dict) else []
        output = [
            {
                "title": e.get("title"),
                "link": e.get("link"),
                "summary": (e.get("summary") or "")[:200],
                "published": e.get("published"),
            }
            for e in entries[:limit]
        ]
        return json.dumps(output)
    except Exception as exc:
        logger.warning("query_rss failed: %s", exc)
        return json.dumps({"error": str(exc)})


@tool
def query_web(query: str, max_results: int = 5) -> str:
    """Search the web using configured search engine. Returns titles, URLs, and snippets."""
    try:
        from alfred.connectors.web_connector import WebConnector

        conn = WebConnector(searx_k=max_results)
        response = conn.search(query=query, num_results=max_results)
        output = [
            {
                "title": hit.title,
                "url": hit.url,
                "snippet": (hit.snippet or "")[:200],
                "source": hit.source,
            }
            for hit in response.hits[:max_results]
        ]
        return json.dumps(output)
    except Exception as exc:
        logger.warning("query_web failed: %s", exc)
        return json.dumps({"error": str(exc)})


@tool
def query_wikipedia(query: str, max_results: int = 3) -> str:
    """Search Wikipedia for articles. Returns page titles, summaries, and URLs."""
    try:
        from alfred.connectors.wikipedia_connector import WikipediaClient

        client = WikipediaClient(top_k_results=max_results)
        docs = client.search(query)
        output = [
            {
                "title": doc.metadata.get("title"),
                "summary": (doc.page_content or "")[:300],
                "source": doc.metadata.get("source"),
            }
            for doc in docs[:max_results]
        ]
        return json.dumps(output)
    except Exception as exc:
        logger.warning("query_wikipedia failed: %s", exc)
        return json.dumps({"error": str(exc)})


@tool
def query_github(query: str, repo: str | None = None, limit: int = 5) -> str:
    """List GitHub issues for a repo and filter client-side by query.

    ``repo`` must be in ``owner/name`` form. Global cross-repo search is not yet
    supported by the underlying connector.
    """
    try:
        from alfred.connectors.github_connector import GitHubClient

        if not repo or "/" not in repo:
            return json.dumps({
                "error": "query_github requires repo='owner/name'",
                "hint": "Cross-repo GitHub search is not yet implemented.",
            })
        owner, name = repo.split("/", 1)

        client = GitHubClient()
        # list_issues paginates fully; cap to a reasonable window before filtering
        issues = client.list_issues(owner, name, state="all", per_page=100)

        q = (query or "").lower().strip()
        if q:
            issues = [
                i
                for i in issues
                if q in (i.get("title") or "").lower()
                or q in (i.get("body") or "").lower()
            ]

        output = [
            {
                "title": i.get("title"),
                "url": i.get("html_url"),
                "state": i.get("state"),
                "created_at": i.get("created_at"),
            }
            for i in issues[:limit]
        ]
        return json.dumps(output)
    except Exception as exc:
        logger.warning("query_github failed: %s", exc)
        return json.dumps({"error": str(exc), "hint": "Check GITHUB_TOKEN is set"})


@tool
def query_linear(query: str, team_id: str | None = None, limit: int = 10) -> str:
    """List Linear issues and filter client-side by query / team.

    The Linear connector does not yet support server-side keyword search, so we
    fetch a recent window of issues and filter in Python.
    """
    try:
        from alfred.connectors.linear_connector import LinearConnector
        from alfred.core.settings import settings

        token = (
            settings.linear_api_key.get_secret_value() if settings.linear_api_key else None
        )
        if not token:
            return json.dumps({
                "error": "LINEAR_API_KEY is not configured",
                "hint": "Set LINEAR_API_KEY to enable Linear queries.",
            })

        conn = LinearConnector(token=token)
        # Over-fetch so client-side filtering still produces ~limit results
        issues = conn.get_all_issues(include_comments=False, limit=max(limit * 5, 50))

        q = (query or "").lower().strip()
        if q:
            issues = [
                i
                for i in issues
                if q in (i.get("title") or "").lower()
                or q in (i.get("description") or "").lower()
            ]
        if team_id:
            issues = [
                i for i in issues if (i.get("team") or {}).get("id") == team_id
            ]

        output = [
            {
                "id": i.get("id"),
                "title": i.get("title"),
                "identifier": i.get("identifier"),
                "state": (i.get("state") or {}).get("name"),
                "url": i.get("url"),
            }
            for i in issues[:limit]
        ]
        return json.dumps(output)
    except Exception as exc:
        logger.warning("query_linear failed: %s", exc)
        return json.dumps({"error": str(exc), "hint": "Check LINEAR_API_KEY is set"})


@tool
def query_semantic_scholar(query: str, limit: int = 5) -> str:
    """Search Semantic Scholar for academic papers. Returns titles, authors, abstracts, and citation counts."""
    try:
        from alfred.connectors.semantic_scholar_connector import SemanticScholarClient

        papers = SemanticScholarClient().search_by_keyword(keyword=query, limit=limit)
        output = [
            {
                "title": p.get("title"),
                "authors": [a.get("name") for a in p.get("authors", [])],
                "abstract": p.get("abstract", "")[:300] if p.get("abstract") else "",
                "year": p.get("year"),
                "citation_count": p.get("citationCount", 0),
                "paper_id": p.get("paperId"),
            }
            for p in papers[:limit]
        ]
        return json.dumps(output)
    except Exception as exc:
        logger.warning("query_semantic_scholar failed: %s", exc)
        return json.dumps({"error": str(exc)})


# List of all connector tools for agent registration
CONNECTOR_TOOLS = [
    query_notion,
    query_readwise,
    query_arxiv,
    query_rss,
    query_web,
    query_wikipedia,
    query_github,
    query_linear,
    query_semantic_scholar,
]
