"""Hypothes.is API connector for Alfred.

Fetches annotations and user profile from the Hypothes.is public API.
Auth via Bearer token.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from alfred.core.settings import settings

logger = logging.getLogger(__name__)

HYPOTHESIS_API_URL = "https://api.hypothes.is/api"


class HypothesisClient:
    """Sync client for the Hypothes.is API."""

    def __init__(
        self,
        token: str | None = None,
        *,
        timeout_seconds: int = 30,
    ) -> None:
        configured = (
            settings.hypothesis_token.get_secret_value()
            if hasattr(settings, "hypothesis_token") and settings.hypothesis_token
            else None
        )
        self._token = token or configured
        if not self._token:
            raise RuntimeError("HYPOTHESIS_TOKEN is not configured")

        self._timeout = timeout_seconds
        self._headers = {
            "Authorization": f"Bearer {self._token}",
            "Accept": "application/json",
        }

    def _get(self, path: str, params: dict[str, Any] | None = None) -> httpx.Response:
        resp = httpx.get(
            f"{HYPOTHESIS_API_URL}{path}",
            headers=self._headers,
            params=params,
            timeout=self._timeout,
        )
        resp.raise_for_status()
        return resp

    def get_user_profile(self) -> dict[str, Any]:
        """GET /api/profile -- returns user info including userid."""
        resp = self._get("/profile")
        return resp.json()

    def search_annotations(
        self,
        *,
        user: str | None = None,
        limit: int = 200,
        offset: int = 0,
        sort: str = "updated",
        order: str = "desc",
        search_after: str | None = None,
    ) -> list[dict[str, Any]]:
        """Search annotations via GET /api/search.

        Args:
            user: Filter by user ID (e.g. ``acct:user@hypothes.is``).
            limit: Max results per request (API max is 200).
            offset: Result offset for pagination.
            sort: Sort field ('created', 'updated', 'id', 'group', 'user').
            order: Sort order ('asc' or 'desc').
            search_after: Opaque cursor for keyset pagination.

        Returns:
            List of annotation dicts.
        """
        params: dict[str, Any] = {
            "limit": min(limit, 200),
            "offset": offset,
            "sort": sort,
            "order": order,
        }
        if user:
            params["user"] = user
        if search_after:
            params["search_after"] = search_after

        resp = self._get("/search", params=params)
        data = resp.json()
        return data.get("rows", [])

    def search_all(self, *, user: str | None = None) -> list[dict[str, Any]]:
        """Paginate through all annotations for a user.

        Uses offset-based pagination (the Hypothes.is search API supports
        offset up to 9800; for very large collections, keyset pagination
        via ``search_after`` is used as fallback).

        Args:
            user: Filter by user ID. If None, fetches the authenticated
                  user's profile first.

        Returns:
            Complete list of annotation dicts.
        """
        all_annotations: list[dict[str, Any]] = []
        page_size = 200
        offset = 0

        while True:
            batch = self.search_annotations(
                user=user,
                limit=page_size,
                offset=offset,
            )
            if not batch:
                break

            all_annotations.extend(batch)
            logger.debug(
                "Hypothesis: fetched %d annotations (offset=%d)", len(batch), offset
            )

            if len(batch) < page_size:
                break

            offset += page_size

            # Hypothes.is caps offset at this value; switch to search_after
            _HYPOTHESIS_MAX_OFFSET = 9800
            if offset >= _HYPOTHESIS_MAX_OFFSET and batch:
                logger.info(
                    "Hypothesis: switching to search_after pagination at offset %d",
                    offset,
                )
                return all_annotations + self._paginate_search_after(
                    user=user, last_item=batch[-1]
                )

        logger.info("Hypothesis: retrieved %d total annotations", len(all_annotations))
        return all_annotations

    def _paginate_search_after(
        self,
        *,
        user: str | None,
        last_item: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """Continue pagination using the search_after parameter."""
        results: list[dict[str, Any]] = []
        search_after = last_item.get("updated", last_item.get("created", ""))
        page_size = 200

        while search_after:
            params: dict[str, Any] = {
                "limit": page_size,
                "sort": "updated",
                "order": "desc",
                "search_after": search_after,
            }
            if user:
                params["user"] = user

            resp = self._get("/search", params=params)
            data = resp.json()
            batch = data.get("rows", [])

            if not batch:
                break

            results.extend(batch)
            logger.debug(
                "Hypothesis (search_after): fetched %d annotations", len(batch)
            )

            if len(batch) < page_size:
                break

            search_after = batch[-1].get("updated", batch[-1].get("created", ""))

        return results


__all__ = ["HypothesisClient"]
