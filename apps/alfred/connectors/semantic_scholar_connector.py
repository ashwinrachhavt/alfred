"""Semantic Scholar API connector for Alfred.

Fetches academic papers, author information, and citation data
from the Semantic Scholar Academic Graph API.

Free tier: 100 requests per 5 minutes (no key required).
Authenticated tier: higher limits with an API key.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from alfred.core.settings import settings

logger = logging.getLogger(__name__)

S2_BASE_URL = "https://api.semanticscholar.org/graph/v1"

_DEFAULT_PAPER_FIELDS = (
    "paperId,title,abstract,authors,year,citationCount,"
    "url,openAccessPdf,fieldsOfStudy,publicationDate"
)
_DEFAULT_PAPER_DETAIL_FIELDS = f"{_DEFAULT_PAPER_FIELDS},tldr"
_DEFAULT_AUTHOR_PAPER_FIELDS = "paperId,title,abstract,year,citationCount,url"


class SemanticScholarClient:
    """Sync client for the Semantic Scholar Academic Graph API."""

    def __init__(
        self,
        api_key: str | None = None,
        *,
        timeout_seconds: int = 30,
    ) -> None:
        configured = settings.semantic_scholar_api_key if settings.semantic_scholar_api_key else None
        self._api_key = api_key or configured
        self._timeout = timeout_seconds
        self._headers: dict[str, str] = {}
        if self._api_key:
            self._headers["x-api-key"] = self._api_key

    def _get(self, url: str, params: dict[str, Any] | None = None) -> httpx.Response:
        resp = httpx.get(url, headers=self._headers, params=params, timeout=self._timeout)
        resp.raise_for_status()
        return resp

    def search_papers(
        self,
        query: str,
        *,
        limit: int = 10,
        offset: int = 0,
        fields: str = _DEFAULT_PAPER_FIELDS,
    ) -> list[dict[str, Any]]:
        """Search for papers matching a query string.

        Args:
            query: Search query string.
            limit: Maximum number of results (default 10).
            offset: Pagination offset.
            fields: Comma-separated list of fields to return.

        Returns:
            List of paper dicts from the ``data`` key of the API response.
        """
        params: dict[str, Any] = {
            "query": query,
            "limit": min(limit, 100),
            "offset": offset,
            "fields": fields,
        }
        resp = self._get(f"{S2_BASE_URL}/paper/search", params=params)
        data = resp.json()
        return data.get("data", [])

    def get_paper(
        self,
        paper_id: str,
        *,
        fields: str = _DEFAULT_PAPER_DETAIL_FIELDS,
    ) -> dict[str, Any]:
        """Get detailed information for a specific paper.

        Args:
            paper_id: Semantic Scholar paper ID, DOI, ArXiv ID, etc.
            fields: Comma-separated list of fields to return.

        Returns:
            Paper metadata dict.
        """
        resp = self._get(f"{S2_BASE_URL}/paper/{paper_id}", params={"fields": fields})
        return resp.json()

    def get_author_papers(
        self,
        author_id: str,
        *,
        limit: int = 100,
        fields: str = _DEFAULT_AUTHOR_PAPER_FIELDS,
    ) -> list[dict[str, Any]]:
        """Get papers by a specific author.

        Args:
            author_id: Semantic Scholar author ID.
            limit: Maximum number of papers to return.
            fields: Comma-separated list of fields to return.

        Returns:
            List of paper dicts.
        """
        params: dict[str, Any] = {
            "limit": min(limit, 1000),
            "fields": fields,
        }
        resp = self._get(f"{S2_BASE_URL}/author/{author_id}/papers", params=params)
        data = resp.json()
        return data.get("data", [])

    def search_by_keyword(
        self,
        keyword: str,
        *,
        year: str | None = None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """Convenience method: search papers with optional year filter.

        Args:
            keyword: Search keyword.
            year: Optional year or year range (e.g., "2020", "2019-2023").
            limit: Maximum number of results.

        Returns:
            List of paper dicts.
        """
        params: dict[str, Any] = {
            "query": keyword,
            "limit": min(limit, 100),
            "fields": _DEFAULT_PAPER_FIELDS,
        }
        if year:
            params["year"] = year
        resp = self._get(f"{S2_BASE_URL}/paper/search", params=params)
        data = resp.json()
        return data.get("data", [])


__all__ = ["SemanticScholarClient"]
