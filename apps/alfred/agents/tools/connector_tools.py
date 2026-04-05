"""Connector agent tools -- query external knowledge sources.

Tools for fetching content from Notion, Readwise, arXiv, RSS, web search,
Wikipedia, GitHub, Linear, and Semantic Scholar. All connectors are lazy-imported
to avoid import-time failures when API keys aren't configured.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from langchain_core.tools import tool

logger = logging.getLogger(__name__)


@tool
def query_notion(query: str | None = None, page_size: int = 10) -> str:
    """Fetch pages from Notion workspace. Returns page titles, content previews, and URLs."""
    try:
        from alfred.connectors.notion_history import NotionHistoryConnector
        import asyncio

        async def _fetch():
            async with NotionHistoryConnector(page_size=page_size) as conn:
                pages = []
                async for page in conn.search_pages(query=query or ""):
                    pages.append({
                        "id": page.get("id"),
                        "title": page.get("title", "Untitled"),
                        "url": page.get("url"),
                        "last_edited": page.get("last_edited_time"),
                    })
                    if len(pages) >= page_size:
                        break
                return pages

        result = asyncio.run(_fetch())
        return json.dumps(result[:page_size])
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
        from alfred.connectors.rss_connector import RSSConnector

        conn = RSSConnector()
        entries = conn.fetch_feed(feed_url)
        output = [
            {
                "title": e.get("title"),
                "link": e.get("link"),
                "summary": e.get("summary", "")[:200],
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

        conn = WebConnector()
        results = conn.search(query=query, max_results=max_results)
        output = [
            {
                "title": r.get("title"),
                "url": r.get("url"),
                "snippet": r.get("snippet", "")[:200],
            }
            for r in results[:max_results]
        ]
        return json.dumps(output)
    except Exception as exc:
        logger.warning("query_web failed: %s", exc)
        return json.dumps({"error": str(exc)})


@tool
def query_wikipedia(query: str, max_results: int = 3) -> str:
    """Search Wikipedia for articles. Returns page titles, summaries, and URLs."""
    try:
        from alfred.connectors.wikipedia_connector import search

        docs = search(query=query, max_results=max_results)
        output = [
            {
                "title": doc.metadata.get("title"),
                "summary": doc.page_content[:300] if doc.page_content else "",
                "source": doc.metadata.get("source"),
            }
            for doc in docs
        ]
        return json.dumps(output)
    except Exception as exc:
        logger.warning("query_wikipedia failed: %s", exc)
        return json.dumps({"error": str(exc)})


@tool
def query_github(query: str, repo: str | None = None, limit: int = 5) -> str:
    """Search GitHub issues, PRs, or code. Optionally filter by repo (owner/name)."""
    try:
        from alfred.connectors.github_connector import GitHubConnector

        conn = GitHubConnector()
        if repo:
            # Search within a specific repo
            results = conn.search_repo_issues(repo=repo, query=query, limit=limit)
        else:
            # Global search (requires more specific implementation)
            results = []
            logger.warning("Global GitHub search not yet implemented, specify repo")

        output = [
            {
                "title": r.get("title"),
                "url": r.get("html_url"),
                "state": r.get("state"),
                "created_at": r.get("created_at"),
            }
            for r in results[:limit]
        ]
        return json.dumps(output)
    except Exception as exc:
        logger.warning("query_github failed: %s", exc)
        return json.dumps({"error": str(exc), "hint": "Check GITHUB_TOKEN is set"})


@tool
def query_linear(query: str, team_id: str | None = None, limit: int = 10) -> str:
    """Search Linear issues. Optionally filter by team ID."""
    try:
        from alfred.connectors.linear_connector import LinearConnector

        conn = LinearConnector()
        issues = conn.search_issues(query=query, team_id=team_id, limit=limit)
        output = [
            {
                "id": i.get("id"),
                "title": i.get("title"),
                "identifier": i.get("identifier"),
                "state": i.get("state", {}).get("name"),
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
        from alfred.connectors.semantic_scholar_connector import search_by_keyword

        papers = search_by_keyword(query=query, limit=limit)
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
