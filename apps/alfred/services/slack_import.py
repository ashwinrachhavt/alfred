"""Ingest Slack channel history and bookmarks into Alfred's document store.

Imports conversations and bookmarks from Slack channels using a stable
hash per document to support idempotent upserts.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from alfred.connectors.slack_connector import SlackClient
from alfred.schemas.documents import DocumentIngest
from alfred.schemas.imports import (
    CONTENT_TYPE_SLACK_BOOKMARK,
    CONTENT_TYPE_SLACK_CHANNEL,
    ImportStats,
)
from alfred.services.doc_storage_pg import DocStorageService

logger = logging.getLogger(__name__)


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------


def _render_messages_markdown(
    messages: list[dict[str, Any]],
    channel_name: str,
) -> str:
    """Render a list of Slack messages as a chronological Markdown document."""
    lines: list[str] = [f"# #{channel_name}", ""]

    # Slack returns newest-first; reverse for chronological order.
    for msg in reversed(messages):
        ts = msg.get("ts", "")
        try:
            dt = datetime.fromtimestamp(float(ts), tz=UTC)
            time_str = dt.strftime("%Y-%m-%d %H:%M:%S UTC")
        except (ValueError, OSError):
            time_str = ts

        user = msg.get("user") or msg.get("username") or "unknown"
        text = (msg.get("text") or "").strip()
        lines.append(f"**{user}** ({time_str}):")
        lines.append(text)
        lines.append("")

    return "\n".join(lines)


# ------------------------------------------------------------------
# Channel history import
# ------------------------------------------------------------------


def import_slack_channels(
    *,
    doc_store: DocStorageService,
    token: str | None = None,
    channel_ids: list[str] | None = None,
    limit: int | None = None,
    since: str | None = None,
) -> dict[str, Any]:
    """Import Slack channel history into the document store.

    Args:
        doc_store: The document storage service.
        token: Optional explicit Slack API token.
        channel_ids: Specific channel IDs to import. If *None*, all
            discoverable channels are imported.
        limit: Max messages to fetch per channel.
        since: Unix timestamp string — only messages after this time.

    Returns:
        Summary dict with ``ok``, ``created``, ``updated``, etc.
    """
    client = SlackClient(token)

    # Discover channels if none specified.
    if channel_ids:
        channels = [{"id": cid} for cid in channel_ids]
    else:
        channels = client.list_channels()

    stats = ImportStats()

    for ch in channels:
        channel_id = ch["id"]
        try:
            info = client.channel_info(channel_id)
            channel_name = info.get("name", channel_id)

            history_kwargs: dict[str, Any] = {}
            if limit is not None:
                history_kwargs["limit"] = limit
            if since is not None:
                history_kwargs["oldest"] = since

            messages = client.channel_history(channel_id, **history_kwargs)
            if not messages:
                stats.skipped += 1
                logger.debug("No messages in channel %s", channel_name)
                continue

            markdown = _render_messages_markdown(messages, channel_name)
            stable_hash = f"slack:channel:{channel_id}"
            title = f"Slack — #{channel_name}"
            url = f"https://app.slack.com/client/{channel_id}"

            topic = (info.get("topic") or {}).get("value", "")
            purpose = (info.get("purpose") or {}).get("value", "")
            member_count = info.get("num_members", 0)

            meta = {
                "source": "slack",
                "channel_id": channel_id,
                "channel_name": channel_name,
                "topic": topic,
                "purpose": purpose,
                "member_count": member_count,
                "message_count": len(messages),
            }

            ingest = DocumentIngest(
                source_url=url,
                title=title,
                content_type=CONTENT_TYPE_SLACK_CHANNEL,
                raw_markdown=markdown,
                cleaned_text=markdown,
                hash=stable_hash,
                metadata=meta,
            )

            res = doc_store.ingest_document_store_only(ingest)
            doc_id = str(res["id"])
            if res.get("duplicate"):
                try:
                    doc_store.update_document_text(
                        doc_id,
                        title=title,
                        cleaned_text=markdown,
                        raw_markdown=markdown,
                        metadata_update=meta,
                    )
                    stats.updated += 1
                except Exception:
                    logger.debug("Skipping update for duplicate %s", doc_id)
                    stats.skipped += 1
            else:
                stats.created += 1

            stats.documents.append({"channel": channel_name, "document_id": doc_id})
        except Exception as exc:
            logger.exception("Slack channel import failed for %s", channel_id)
            stats.errors.append({"channel": channel_id, "error": str(exc)})

    result = stats.to_dict()
    result["type"] = "slack_channel"
    return result


# ------------------------------------------------------------------
# Bookmark import
# ------------------------------------------------------------------


def import_slack_bookmarks(
    *,
    doc_store: DocStorageService,
    token: str | None = None,
    channel_ids: list[str] | None = None,
) -> dict[str, Any]:
    """Import Slack bookmarks into the document store.

    Args:
        doc_store: The document storage service.
        token: Optional explicit Slack API token.
        channel_ids: Channels to fetch bookmarks from. If *None*, all
            discoverable channels are scanned.

    Returns:
        Summary dict with ``ok``, ``created``, ``updated``, etc.
    """
    client = SlackClient(token)

    if channel_ids:
        channels = [{"id": cid} for cid in channel_ids]
    else:
        channels = client.list_channels()

    stats = ImportStats()

    for ch in channels:
        channel_id = ch["id"]
        try:
            info = client.channel_info(channel_id)
            channel_name = info.get("name", channel_id)
            bookmarks = client.list_bookmarks(channel_id)

            if not bookmarks:
                stats.skipped += 1
                continue

            for bm in bookmarks:
                bookmark_id = bm.get("id", "")
                bm_title = bm.get("title") or bm.get("link", "Untitled Bookmark")
                bm_link = bm.get("link", "")
                stable_hash = f"slack:bookmark:{bookmark_id}"

                content_lines = [
                    f"# {bm_title}",
                    "",
                    f"**Channel:** #{channel_name}",
                    f"**Link:** {bm_link}" if bm_link else "",
                ]
                markdown = "\n".join(line for line in content_lines if line is not None)

                meta = {
                    "source": "slack",
                    "bookmark_id": bookmark_id,
                    "channel_id": channel_id,
                    "channel_name": channel_name,
                    "link": bm_link,
                    "type": bm.get("type", ""),
                }

                ingest = DocumentIngest(
                    source_url=bm_link or f"https://app.slack.com/client/{channel_id}",
                    title=bm_title,
                    content_type=CONTENT_TYPE_SLACK_BOOKMARK,
                    raw_markdown=markdown,
                    cleaned_text=markdown,
                    hash=stable_hash,
                    metadata=meta,
                )

                res = doc_store.ingest_document_store_only(ingest)
                doc_id = str(res["id"])
                if res.get("duplicate"):
                    try:
                        doc_store.update_document_text(
                            doc_id,
                            title=bm_title,
                            cleaned_text=markdown,
                            raw_markdown=markdown,
                            metadata_update=meta,
                        )
                        stats.updated += 1
                    except Exception:
                        logger.debug("Skipping update for duplicate %s", doc_id)
                        stats.skipped += 1
                else:
                    stats.created += 1

                stats.documents.append({
                    "channel": channel_name,
                    "bookmark": bm_title,
                    "document_id": doc_id,
                })
        except Exception as exc:
            logger.exception("Slack bookmark import failed for channel %s", channel_id)
            stats.errors.append({"channel": channel_id, "error": str(exc)})

    result = stats.to_dict()
    result["type"] = "slack_bookmark"
    return result


# ------------------------------------------------------------------
# Combined entry point
# ------------------------------------------------------------------


def import_slack(
    *,
    doc_store: DocStorageService,
    token: str | None = None,
    channel_ids: list[str] | None = None,
    limit: int | None = None,
    since: str | None = None,
) -> dict[str, Any]:
    """Import Slack channels and bookmarks into the document store.

    This is the main entry point that orchestrates both channel history
    and bookmark imports.
    """
    channels_result = import_slack_channels(
        doc_store=doc_store,
        token=token,
        channel_ids=channel_ids,
        limit=limit,
        since=since,
    )
    bookmarks_result = import_slack_bookmarks(
        doc_store=doc_store,
        token=token,
        channel_ids=channel_ids,
    )

    return {
        "ok": True,
        "channels": channels_result,
        "bookmarks": bookmarks_result,
    }


__all__ = [
    "import_slack",
    "import_slack_bookmarks",
    "import_slack_channels",
]
