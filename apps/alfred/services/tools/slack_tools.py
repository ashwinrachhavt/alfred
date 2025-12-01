from __future__ import annotations

import logging
from typing import Optional

from alfred.core import agno_tracing
from alfred.services.slack import SlackService

from ._tooling import agno_tool as tool

logger = logging.getLogger(__name__)


@tool()
def slack_send_message(channel: str, text: str, thread_ts: Optional[str] = None) -> str:
    """Send a message to a Slack channel (or thread).

    Use this to notify a Slack channel or reply in a thread. Requires
    `SLACK_API_KEY` to be configured.
    """
    ch = (channel or "").strip()
    if not ch:
        return "### Slack\n\n⚠️ Missing required parameter: channel"
    if not (text or "").strip():
        return "### Slack\n\n⚠️ Missing required parameter: text"

    try:
        svc = SlackService()
        result = svc.send_message(channel=ch, text=text, thread_ts=thread_ts)
        link = result.get("permalink")
        ts = result.get("ts")
        if link:
            out = (
                "### Slack\n\n"
                f"✅ Message sent to `{ch}`.  \
Permalink: {link}\n"
            )
            try:
                agno_tracing.log_tool_call(
                    name="slack_send_message",
                    args={"channel": ch, "thread_ts": thread_ts is not None},
                    result={"permalink": link},
                )
            except Exception:
                pass
            return out
        out = "### Slack\n\n" f"✅ Message sent to `{ch}`.  \n" f"Timestamp: `{ts}`"
        try:
            agno_tracing.log_tool_call(
                name="slack_send_message",
                args={"channel": ch, "thread_ts": thread_ts is not None},
                result={"ts": ts},
            )
        except Exception:
            pass
        return out
    except Exception as exc:  # pragma: no cover - defensive path
        logger.warning("slack send failed: %s", exc)
        try:
            agno_tracing.log_tool_call(
                name="slack_send_message",
                args={"channel": ch, "thread_ts": thread_ts is not None},
                result=None,
                error=str(exc),
            )
        except Exception:
            pass
        return "### Slack\n\n" f"⚠️ Failed to send message to `{ch}`. Error: {exc}"
