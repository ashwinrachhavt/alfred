"""Ingest RSS/Atom feed entries into Alfred's document store.

Each feed entry becomes a single document. Supports multiple feed URLs
and deduplication via stable hashes derived from entry links.
"""

from __future__ import annotations

import hashlib
import logging
from typing import Any

from alfred.connectors.rss_connector import RSSClient
from alfred.schemas.documents import DocumentIngest
from alfred.services.doc_storage_pg import DocStorageService

logger = logging.getLogger(__name__)


def _stable_hash(entry_link: str) -> str:
    """Produce a stable short hash for an RSS entry based on its URL."""
    digest = hashlib.md5(entry_link.encode()).hexdigest()
    return f"rss:{digest}"


def _render_entry_markdown(entry: dict[str, Any], feed_title: str) -> str:
    """Render an RSS/Atom entry as Markdown."""
    title = entry.get("title") or "Untitled"
    link = entry.get("link") or ""
    author = entry.get("author")
    published = entry.get("published")
    categories = entry.get("categories") or []

    lines = [f"# {title}"]
    meta_parts: list[str] = []
    if author:
        meta_parts.append(f"**Author:** {author}")
    if published:
        meta_parts.append(f"**Published:** {published}")
    meta_parts.append(f"**Feed:** {feed_title}")
    if link:
        meta_parts.append(f"**Link:** {link}")
    if meta_parts:
        lines.append("  ".join(meta_parts))
    if categories:
        lines.append(f"*Tags: {', '.join(categories)}*")
    lines.append("")

    # Prefer full content, fall back to summary
    body = entry.get("content") or entry.get("summary") or ""
    if body:
        lines.append(body)

    return "\n".join(lines)


def import_rss(
    *,
    doc_store: DocStorageService,
    feed_urls: list[str],
    limit: int | None = None,
) -> dict[str, Any]:
    """Import entries from RSS/Atom feeds into the document store.

    Args:
        doc_store: The document storage service.
        feed_urls: List of feed URLs to fetch and import.
        limit: Max total entries to import across all feeds.

    Returns:
        Summary dict with ok, created, updated, skipped, errors, documents.
    """
    client = RSSClient()

    created = 0
    updated = 0
    skipped = 0
    errors: list[dict[str, str]] = []
    documents: list[dict[str, str]] = []
    total_processed = 0

    feeds = client.fetch_multiple(feed_urls)

    for feed in feeds:
        feed_title = feed.get("title", "Unknown Feed")
        entries = feed.get("entries", [])

        for entry in entries:
            if limit is not None and total_processed >= limit:
                break

            entry_link = entry.get("link", "")
            if not entry_link:
                skipped += 1
                continue

            try:
                title = entry.get("title") or "Untitled"
                markdown = _render_entry_markdown(entry, feed_title)
                cleaned_text = markdown.strip()

                if not cleaned_text:
                    skipped += 1
                    continue

                stable_hash = _stable_hash(entry_link)
                categories = entry.get("categories") or []

                rss_meta: dict[str, Any] = {
                    "feed_title": feed_title,
                    "feed_link": feed.get("link"),
                    "published": entry.get("published"),
                    "author": entry.get("author"),
                }

                ingest = DocumentIngest(
                    source_url=entry_link,
                    title=title,
                    content_type="rss_entry",
                    raw_markdown=markdown,
                    cleaned_text=cleaned_text,
                    hash=stable_hash,
                    tags=categories or None,
                    metadata={"source": "rss", "rss": rss_meta},
                )

                res = doc_store.ingest_document_store_only(ingest)
                doc_id = str(res["id"])

                if res.get("duplicate"):
                    updated += 1
                    doc_store.update_document_text(
                        doc_id,
                        title=title,
                        cleaned_text=cleaned_text,
                        raw_markdown=markdown,
                        metadata_update={"source": "rss", "rss": rss_meta},
                    )
                else:
                    created += 1

                documents.append({"entry_link": entry_link, "document_id": doc_id})
                total_processed += 1

            except Exception as exc:
                logger.exception("RSS import failed for entry: %s", entry_link)
                errors.append({"entry_link": entry_link, "error": str(exc)})

        if limit is not None and total_processed >= limit:
            break

    return {
        "ok": True,
        "created": created,
        "updated": updated,
        "skipped": skipped,
        "errors": errors,
        "documents": documents,
    }


__all__ = ["import_rss"]
