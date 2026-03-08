"""Readwise API connector for Alfred.

Fetches books and highlights from a user's Readwise library.
Uses the Export API for efficient bulk retrieval with incremental sync support.
"""

from __future__ import annotations

import logging
import time
from typing import Any

import httpx

from alfred.core.settings import settings

logger = logging.getLogger(__name__)

READWISE_BASE_URL = "https://readwise.io/api/v2"


class ReadwiseClient:
    """Sync client for the Readwise API."""

    def __init__(
        self,
        token: str | None = None,
        *,
        timeout_seconds: int = 30,
        sleep_between_pages: float = 1.0,
    ) -> None:
        configured = settings.readwise_token.get_secret_value() if settings.readwise_token else None
        self._token = token or configured
        if not self._token:
            raise RuntimeError("READWISE_TOKEN is not configured")
        self._timeout = timeout_seconds
        self._sleep = max(0.0, sleep_between_pages)
        self._headers = {"Authorization": f"Token {self._token}"}

    def export_highlights(
        self,
        *,
        updated_after: str | None = None,
        book_ids: list[int] | None = None,
    ) -> list[dict[str, Any]]:
        """Fetch all books with their highlights using the Export API.

        This is the most efficient endpoint for bulk retrieval.
        Supports incremental sync via `updated_after` (ISO 8601).

        Returns list of book dicts, each containing a `highlights` array.
        """
        full_data: list[dict[str, Any]] = []
        params: dict[str, Any] = {}
        if updated_after:
            params["updatedAfter"] = updated_after
        if book_ids:
            params["ids"] = ",".join(str(bid) for bid in book_ids)

        while True:
            resp = httpx.get(
                f"{READWISE_BASE_URL}/export/",
                headers=self._headers,
                params=params,
                timeout=self._timeout,
            )
            resp.raise_for_status()
            data = resp.json()

            full_data.extend(data.get("results", []))

            next_cursor = data.get("nextPageCursor")
            if not next_cursor:
                break

            params["pageCursor"] = next_cursor
            if self._sleep > 0:
                time.sleep(self._sleep)

        logger.info("Readwise export: fetched %d books with highlights", len(full_data))
        return full_data

    def list_books(
        self,
        *,
        category: str | None = None,
        updated_after: str | None = None,
        page_size: int = 100,
    ) -> list[dict[str, Any]]:
        """Fetch books/articles from the Readwise library.

        Args:
            category: Filter by 'books', 'articles', 'tweets', 'supplementals', 'podcasts'.
            updated_after: ISO 8601 datetime for incremental sync.
            page_size: Results per page (max 1000).
        """
        all_books: list[dict[str, Any]] = []
        params: dict[str, Any] = {"page_size": min(page_size, 1000)}
        if category:
            params["category"] = category
        if updated_after:
            params["updated__gt"] = updated_after

        page = 1
        while True:
            params["page"] = page
            resp = httpx.get(
                f"{READWISE_BASE_URL}/books/",
                headers=self._headers,
                params=params,
                timeout=self._timeout,
            )
            resp.raise_for_status()
            data = resp.json()

            all_books.extend(data.get("results", []))

            if not data.get("next"):
                break
            page += 1
            if self._sleep > 0:
                time.sleep(self._sleep)

        return all_books

    def list_highlights(
        self,
        *,
        book_id: int | None = None,
        updated_after: str | None = None,
        page_size: int = 100,
    ) -> list[dict[str, Any]]:
        """Fetch individual highlights, optionally filtered by book."""
        all_highlights: list[dict[str, Any]] = []
        params: dict[str, Any] = {"page_size": min(page_size, 1000)}
        if book_id:
            params["book_id"] = book_id
        if updated_after:
            params["updated__gt"] = updated_after

        page = 1
        while True:
            params["page"] = page
            resp = httpx.get(
                f"{READWISE_BASE_URL}/highlights/",
                headers=self._headers,
                params=params,
                timeout=self._timeout,
            )
            resp.raise_for_status()
            data = resp.json()

            all_highlights.extend(data.get("results", []))

            if not data.get("next"):
                break
            page += 1
            if self._sleep > 0:
                time.sleep(self._sleep)

        return all_highlights
