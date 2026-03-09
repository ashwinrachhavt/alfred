"""Pocket API connector for Alfred.

Retrieves saved articles from a user's Pocket account using the Retrieve API.
Pocket uses a custom auth scheme with consumer_key + access_token.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from alfred.core.settings import settings

logger = logging.getLogger(__name__)

POCKET_API_URL = "https://getpocket.com/v3"


class PocketClient:
    """Sync client for the Pocket Retrieve API."""

    def __init__(
        self,
        consumer_key: str | None = None,
        access_token: str | None = None,
        *,
        timeout_seconds: int = 30,
    ) -> None:
        configured_key = (
            settings.pocket_consumer_key.get_secret_value()
            if hasattr(settings, "pocket_consumer_key") and settings.pocket_consumer_key
            else None
        )
        configured_token = (
            settings.pocket_access_token.get_secret_value()
            if hasattr(settings, "pocket_access_token") and settings.pocket_access_token
            else None
        )
        self._consumer_key = consumer_key or configured_key
        self._access_token = access_token or configured_token

        if not self._consumer_key:
            raise RuntimeError("POCKET_CONSUMER_KEY is not configured")
        if not self._access_token:
            raise RuntimeError("POCKET_ACCESS_TOKEN is not configured")

        self._timeout = timeout_seconds
        self._headers = {
            "Content-Type": "application/json; charset=UTF-8",
            "X-Accept": "application/json",
        }

    def retrieve(
        self,
        *,
        state: str = "all",
        count: int = 30,
        offset: int = 0,
        since: int | None = None,
        tag: str | None = None,
        detail_type: str = "complete",
    ) -> list[dict[str, Any]]:
        """Retrieve saved items from Pocket.

        Args:
            state: 'unread', 'archive', or 'all'.
            count: Number of items per request (max varies by API).
            offset: Item offset for pagination.
            since: Unix timestamp; only return items modified since.
            tag: Filter by tag name, or '_untagged_' for untagged items.
            detail_type: 'simple' or 'complete' (includes tags, images, etc.).

        Returns:
            List of item dicts.
        """
        body: dict[str, Any] = {
            "consumer_key": self._consumer_key,
            "access_token": self._access_token,
            "state": state,
            "detailType": detail_type,
            "count": count,
            "offset": offset,
        }
        if since is not None:
            body["since"] = since
        if tag is not None:
            body["tag"] = tag

        resp = httpx.post(
            f"{POCKET_API_URL}/get",
            headers=self._headers,
            json=body,
            timeout=self._timeout,
        )
        resp.raise_for_status()
        data = resp.json()

        item_list = data.get("list", {})
        # Pocket returns a dict keyed by item_id, or an empty list when no results
        if isinstance(item_list, list):
            return []
        return list(item_list.values())

    def retrieve_all(
        self,
        *,
        since: int | None = None,
        tag: str | None = None,
        page_size: int = 30,
    ) -> list[dict[str, Any]]:
        """Retrieve ALL items with automatic pagination.

        Args:
            since: Unix timestamp; only return items modified since.
            tag: Filter by tag name.
            page_size: Items per page (used for internal pagination).

        Returns:
            Complete list of item dicts.
        """
        all_items: list[dict[str, Any]] = []
        offset = 0

        while True:
            batch = self.retrieve(
                state="all",
                count=page_size,
                offset=offset,
                since=since,
                tag=tag,
            )
            if not batch:
                break

            all_items.extend(batch)
            logger.debug("Pocket: fetched %d items (offset=%d)", len(batch), offset)

            if len(batch) < page_size:
                break
            offset += page_size

        logger.info("Pocket: retrieved %d total items", len(all_items))
        return all_items


__all__ = ["PocketClient"]
