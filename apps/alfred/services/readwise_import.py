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
from alfred.schemas.imports import CONTENT_TYPE_READWISE
from alfred.services.base_import import BaseImportService
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


class ReadwiseImportService(BaseImportService):
    """Import Readwise books and highlights into Alfred's document store."""

    def __init__(
        self,
        *,
        doc_store: DocStorageService,
        token: str | None = None,
        category: str | None = None,
        limit: int | None = None,
    ) -> None:
        super().__init__(doc_store=doc_store, source_name="readwise")
        self._token = token
        self._category = category
        self._limit = limit

    def fetch_items(self, *, since: datetime | str | None = None, **kwargs: Any) -> list[dict[str, Any]]:
        client = ReadwiseClient(token=self._token)
        updated_after = None
        if since:
            updated_after = since if isinstance(since, str) else since.isoformat()

        books = client.export_highlights(updated_after=updated_after)

        if self._category:
            books = [b for b in books if b.get("category") == self._category]
        if self._limit is not None:
            books = books[: self._limit]

        return books

    def map_to_document(self, item: dict[str, Any]) -> DocumentIngest:
        book_id = item.get("user_book_id")
        title = item.get("title") or "Untitled"
        markdown = _render_book_markdown(item)

        source_url = (
            item.get("readwise_url") or item.get("source_url") or f"readwise://{book_id}"
        )

        book_tags = item.get("book_tags") or []
        tag_names = [t.get("name") for t in book_tags if t.get("name")]

        readwise_meta = {
            "user_book_id": book_id,
            "category": item.get("category"),
            "source": item.get("source"),
            "author": item.get("author"),
            "cover_image_url": item.get("cover_image_url"),
            "source_url": item.get("source_url"),
            "readwise_url": item.get("readwise_url"),
            "asin": item.get("asin"),
            "num_highlights": len(item.get("highlights") or []),
        }

        return DocumentIngest(
            source_url=source_url,
            title=title,
            content_type=CONTENT_TYPE_READWISE,
            raw_markdown=markdown,
            cleaned_text=markdown.strip(),
            hash=f"readwise:{book_id}",
            tags=tag_names or None,
            metadata={"source": "readwise", "readwise": readwise_meta},
        )

    def item_id(self, item: dict[str, Any]) -> str:
        return str(item.get("user_book_id", "unknown"))


def import_readwise(
    *,
    doc_store: DocStorageService,
    token: str | None = None,
    since: str | datetime | None = None,
    limit: int | None = None,
    category: str | None = None,
) -> dict[str, Any]:
    """Convenience wrapper preserving the existing function signature."""
    svc = ReadwiseImportService(
        doc_store=doc_store, token=token, category=category, limit=limit
    )
    return svc.run_import(since=since)


__all__ = ["ReadwiseImportService", "import_readwise"]
