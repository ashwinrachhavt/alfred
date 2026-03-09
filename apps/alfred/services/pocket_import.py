"""Ingest Pocket saved articles into Alfred's document store.

Each Pocket item becomes a single document. Uses the Pocket Retrieve API
which provides excerpts (not full article content).
"""

from __future__ import annotations

import logging
from typing import Any

from alfred.connectors.pocket_connector import PocketClient
from alfred.schemas.documents import DocumentIngest
from alfred.schemas.imports import CONTENT_TYPE_POCKET_ARTICLE, ImportStats
from alfred.services.doc_storage_pg import DocStorageService

logger = logging.getLogger(__name__)


def _render_pocket_markdown(item: dict[str, Any]) -> str:
    """Render a Pocket item as Markdown."""
    title = item.get("resolved_title") or item.get("given_title") or "Untitled"
    url = item.get("resolved_url") or item.get("given_url") or ""
    excerpt = (item.get("excerpt") or "").strip()
    word_count = item.get("word_count")

    lines = [f"# {title}"]
    meta_parts: list[str] = []
    if url:
        meta_parts.append(f"**URL:** {url}")
    if word_count:
        meta_parts.append(f"**Words:** {word_count}")
    is_article = item.get("is_article")
    if is_article == "1":
        meta_parts.append("**Type:** Article")
    if meta_parts:
        lines.append("  ".join(meta_parts))
    lines.append("")

    if excerpt:
        lines.append(excerpt)

    return "\n".join(lines)


def _extract_tags(item: dict[str, Any]) -> list[str]:
    """Extract tag names from a Pocket item."""
    tags_data = item.get("tags")
    if not tags_data or not isinstance(tags_data, dict):
        return []
    return [tag_info.get("tag", "") for tag_info in tags_data.values() if tag_info.get("tag")]


def import_pocket(
    *,
    doc_store: DocStorageService,
    consumer_key: str | None = None,
    access_token: str | None = None,
    limit: int | None = None,
    since: int | None = None,
    tag: str | None = None,
) -> dict[str, Any]:
    """Import saved items from Pocket into the document store.

    Args:
        doc_store: The document storage service.
        consumer_key: Optional explicit Pocket consumer key.
        access_token: Optional explicit Pocket access token.
        limit: Max number of items to import.
        since: Unix timestamp; only import items modified since.
        tag: Filter by tag name.

    Returns:
        Summary dict with ok, created, updated, skipped, errors, documents.
    """
    client = PocketClient(consumer_key=consumer_key, access_token=access_token)

    if limit is not None:
        items = client.retrieve(count=limit, since=since, tag=tag)
    else:
        items = client.retrieve_all(since=since, tag=tag)

    if limit is not None:
        items = items[:limit]

    stats = ImportStats()

    for item in items:
        item_id = item.get("item_id")
        if not item_id:
            stats.skipped += 1
            continue

        source_url = item.get("resolved_url") or item.get("given_url")
        if not source_url:
            stats.skipped += 1
            continue

        try:
            title = item.get("resolved_title") or item.get("given_title") or "Untitled"
            markdown = _render_pocket_markdown(item)
            cleaned_text = (item.get("excerpt") or markdown).strip()

            if not cleaned_text:
                stats.skipped += 1
                continue

            stable_hash = f"pocket:{item_id}"
            tag_names = _extract_tags(item)

            pocket_meta: dict[str, Any] = {
                "item_id": item_id,
                "time_added": item.get("time_added"),
                "time_updated": item.get("time_updated"),
                "word_count": item.get("word_count"),
                "is_article": item.get("is_article"),
                "given_url": item.get("given_url"),
                "resolved_url": item.get("resolved_url"),
            }

            ingest = DocumentIngest(
                source_url=source_url,
                title=title,
                content_type=CONTENT_TYPE_POCKET_ARTICLE,
                raw_markdown=markdown,
                cleaned_text=cleaned_text,
                hash=stable_hash,
                tags=tag_names or None,
                metadata={"source": "pocket", "pocket": pocket_meta},
            )

            res = doc_store.ingest_document_store_only(ingest)
            doc_id = str(res["id"])

            if res.get("duplicate"):
                try:
                    doc_store.update_document_text(
                        doc_id,
                        title=title,
                        cleaned_text=cleaned_text,
                        raw_markdown=markdown,
                        metadata_update={"source": "pocket", "pocket": pocket_meta},
                    )
                    stats.updated += 1
                except Exception:
                    logger.debug("Skipping update for duplicate %s", doc_id)
                    stats.skipped += 1
            else:
                stats.created += 1

            stats.documents.append({"item_id": str(item_id), "document_id": doc_id})

        except Exception as exc:
            logger.exception("Pocket import failed for item %s", item_id)
            stats.errors.append({"item_id": str(item_id), "error": str(exc)})

    return stats.to_dict()


__all__ = ["import_pocket"]
