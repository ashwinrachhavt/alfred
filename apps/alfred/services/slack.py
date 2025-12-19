"""Minimal Slack service for sending messages.

Wraps `slack_sdk.WebClient.chat_postMessage` and reads the token from
`SLACK_API_KEY` via `alfred.core.settings.settings` by default.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

from alfred.core.settings import settings

logger = logging.getLogger(__name__)


class SlackService:
    """Send messages to Slack channels or threads."""

    def __init__(self, token: Optional[str] = None) -> None:
        configured = settings.slack_api_key.get_secret_value() if settings.slack_api_key else None
        self._token = token or configured
        if not self._token:
            raise ValueError("Slack API key not configured. Set SLACK_API_KEY in the environment.")
        self._client = WebClient(token=self._token)

    def send_message(
        self, channel: str, text: str, *, thread_ts: Optional[str] = None
    ) -> dict[str, Any]:
        """Send a message to a channel. Optionally post in a thread.

        Args:
            channel: Channel ID/name (e.g., "#general" or "C12345").
            text: Message text.
            thread_ts: Optional thread timestamp to reply within a thread.

        Returns:
            Minimal response with ok, channel, ts, and message URL when available.
        """
        try:
            kwargs: dict[str, Any] = {"channel": channel, "text": text}
            if thread_ts:
                kwargs["thread_ts"] = thread_ts
            resp = self._client.chat_postMessage(**kwargs)
            data = resp.data if hasattr(resp, "data") else dict(resp)  # type: ignore
            permalink = None
            try:
                # Best-effort: build a permalink for the posted message
                info = self._client.chat_getPermalink(
                    channel=data["channel"], message_ts=data["ts"]
                )
                permalink = info.get("permalink")
            except Exception:
                pass
            return {
                "ok": bool(data.get("ok", True)),
                "channel": data.get("channel"),
                "ts": data.get("ts"),
                "permalink": permalink,
            }
        except SlackApiError as exc:
            logger.warning("Slack API error sending message: %s", exc)
            raise
