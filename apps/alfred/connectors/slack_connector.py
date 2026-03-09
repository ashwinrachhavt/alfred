"""Slack Web API connector for Alfred.

Provides a synchronous client for fetching channels, messages, bookmarks,
and saved items from the Slack Web API using httpx.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from alfred.core.settings import settings

logger = logging.getLogger(__name__)

SLACK_API_URL = "https://slack.com/api/"


class SlackClient:
    """Sync client for the Slack Web API."""

    def __init__(
        self,
        token: str | None = None,
        *,
        timeout_seconds: int = 30,
    ) -> None:
        configured = settings.slack_api_key.get_secret_value() if settings.slack_api_key else None
        self._token = token or configured
        if not self._token:
            raise RuntimeError("SLACK_API_KEY is not configured")
        self._timeout = timeout_seconds
        self._headers = {
            "Authorization": f"Bearer {self._token}",
            "Content-Type": "application/json; charset=utf-8",
        }

    def _post(self, method: str, data: dict[str, Any] | None = None) -> dict[str, Any]:
        """Send a POST request to a Slack Web API method and return the JSON body.

        Raises ``RuntimeError`` if the Slack API returns ``ok: false``.
        """
        url = f"{SLACK_API_URL}{method}"
        resp = httpx.post(url, headers=self._headers, json=data or {}, timeout=self._timeout)
        resp.raise_for_status()
        body = resp.json()
        if not body.get("ok"):
            error = body.get("error", "unknown_error")
            logger.error("Slack API error on %s: %s", method, error)
            raise RuntimeError(f"Slack API error ({method}): {error}")
        return body

    # ------------------------------------------------------------------
    # Channels
    # ------------------------------------------------------------------

    def list_channels(
        self,
        *,
        types: str = "public_channel,private_channel",
        limit: int = 200,
    ) -> list[dict[str, Any]]:
        """Return all channels, handling cursor-based pagination."""
        all_channels: list[dict[str, Any]] = []
        cursor: str | None = None

        while True:
            data: dict[str, Any] = {"types": types, "limit": limit}
            if cursor:
                data["cursor"] = cursor

            body = self._post("conversations.list", data)
            all_channels.extend(body.get("channels", []))

            cursor = (body.get("response_metadata") or {}).get("next_cursor")
            if not cursor:
                break

        return all_channels

    def channel_history(
        self,
        channel_id: str,
        *,
        limit: int = 200,
        oldest: str | None = None,
    ) -> list[dict[str, Any]]:
        """Fetch message history for a channel, handling cursor-based pagination.

        Args:
            channel_id: The Slack channel ID.
            limit: Max messages per page (up to 200).
            oldest: Unix timestamp string — only messages after this time.
        """
        all_messages: list[dict[str, Any]] = []
        cursor: str | None = None

        while True:
            data: dict[str, Any] = {"channel": channel_id, "limit": limit}
            if oldest:
                data["oldest"] = oldest
            if cursor:
                data["cursor"] = cursor

            body = self._post("conversations.history", data)
            all_messages.extend(body.get("messages", []))

            cursor = (body.get("response_metadata") or {}).get("next_cursor")
            if not cursor:
                break

        return all_messages

    def channel_info(self, channel_id: str) -> dict[str, Any]:
        """Fetch metadata for a single channel."""
        body = self._post("conversations.info", {"channel": channel_id})
        return body.get("channel", {})

    # ------------------------------------------------------------------
    # Bookmarks
    # ------------------------------------------------------------------

    def list_bookmarks(self, channel_id: str) -> list[dict[str, Any]]:
        """List bookmarks for a channel."""
        body = self._post("bookmarks.list", {"channel_id": channel_id})
        return body.get("bookmarks", [])

    # ------------------------------------------------------------------
    # Saved items (stars)
    # ------------------------------------------------------------------

    def list_saved_items(self) -> list[dict[str, Any]]:
        """List starred/saved items for the authenticated user, with pagination."""
        all_items: list[dict[str, Any]] = []
        cursor: str | None = None

        while True:
            data: dict[str, Any] = {}
            if cursor:
                data["cursor"] = cursor

            body = self._post("stars.list", data)
            all_items.extend(body.get("items", []))

            cursor = (body.get("response_metadata") or {}).get("next_cursor")
            if not cursor:
                break

        return all_items


__all__ = [
    "SlackClient",
]
