"""Ingest Readwise highlights into Alfred's document store.

Each book/article becomes a single document containing all its highlights,
rendered as Markdown. Supports incremental sync via the Readwise Export API.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from alfred.connectors.readwise_connector import ReadwiseClient
from alfred.schemas.documents import DocumentIngest
from alfred.services.doc_storage_pg import DocStorageService

logger = logging.getLogger(__name__)


def _render_book_markdown(book: dict[str, Any]) -> str:
    """Render a Readwise book and its highlights as Markdown."""
    title = book.get("title") or "Untitled"
    author = book.get("author") or "Unknown"
    category = book.get("category") or "unknown"
    source = book.get("source") or "unknown"

    lines = [
        f"# {title}",
        f"**Author:** {author}  ",
        f"**Category:** {category} | **Source:** {source}",
        "",
    ]

    doc_note = (book.get("document_note") or "").strip()
    if doc_note:
        lines.extend([f"> {doc_note}", ""])

    highlights = book.get("highlights") or []
    if highlights:
        lines.append(f"## Highlights ({len(highlights)})")
        lines.append("")

        for hl in highlights:
            text = (hl.get("text") or "").strip()
            if not text:
                continue
            lines.append(f"> {text}")
            note = (hl.get("note") or "").strip()
            if note:
                lines.append("")
                lines.append(f"**Note:** {note}")
            tags = hl.get("tags") or []
            if tags:
                tag_names = ", ".join(t.get("name", "") for t in tags if t.get("name"))
                if tag_names:
                    lines.append(f"*Tags: {tag_names}*")
            lines.append("")

    return "\n".join(lines)


def import_readwise(
    *,
    doc_store: DocStorageService,
    token: str | None = None,
    since: str | datetime | None = None,
    limit: int | None = None,
    category: str | None = None,
) -> dict[str, Any]:
    """Import Readwise books and highlights into Alfred's document store.

    Args:
        doc_store: The document storage service.
        token: Optional explicit Readwise API token.
        since: ISO 8601 datetime for incremental sync.
        limit: Max number of books to import.
        category: Filter by category (books, articles, tweets, etc.).
    """
    client = ReadwiseClient(token=token)

    updated_after = None
    if since:
        updated_after = since if isinstance(since, str) else since.isoformat()

    books = client.export_highlights(updated_after=updated_after)

    if category:
        books = [b for b in books if b.get("category") == category]

    if limit is not None:
        books = books[:limit]

    created = 0
    updated = 0
    skipped = 0
    errors: list[dict[str, str]] = []
    documents: list[dict[str, str]] = []

    for book in books:
        book_id = book.get("user_book_id")
        if not book_id:
            skipped += 1
            continue

        highlights = book.get("highlights") or []
        if not highlights:
            skipped += 1
            continue

        try:
            title = book.get("title") or "Untitled"
            markdown = _render_book_markdown(book)
            cleaned_text = markdown.strip()

            source_url = (
                book.get("readwise_url")
                or book.get("source_url")
                or f"readwise://{book_id}"
            )
            stable_hash = f"readwise:{book_id}"

            book_tags = book.get("book_tags") or []
            tag_names = [t.get("name") for t in book_tags if t.get("name")]

            readwise_meta = {
                "user_book_id": book_id,
                "category": book.get("category"),
                "source": book.get("source"),
                "author": book.get("author"),
                "cover_image_url": book.get("cover_image_url"),
                "source_url": book.get("source_url"),
                "readwise_url": book.get("readwise_url"),
                "asin": book.get("asin"),
                "num_highlights": len(highlights),
            }

            ingest = DocumentIngest(
                source_url=source_url,
                title=title,
                content_type="readwise",
                raw_markdown=markdown,
                cleaned_text=cleaned_text,
                hash=stable_hash,
                tags=tag_names or None,
                metadata={"source": "readwise", "readwise": readwise_meta},
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
                        metadata_update={"source": "readwise", "readwise": readwise_meta},
                    )
                    updated += 1
                except Exception:
                    logger.debug("Skipping update for duplicate %s", doc_id)
                    skipped += 1
            else:
                created += 1

            documents.append({"book_id": str(book_id), "document_id": doc_id})

        except Exception as exc:
            logger.exception("Readwise import failed for book %s", book_id)
            errors.append({"book_id": str(book_id), "error": str(exc)})

    return {
        "ok": True,
        "created": created,
        "updated": updated,
        "skipped": skipped,
        "errors": errors,
        "documents": documents,
    }


__all__ = ["import_readwise", "ReadwiseClient"]
