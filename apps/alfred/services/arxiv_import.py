"""Ingest ArXiv papers into Alfred's document store.

Searches ArXiv via the connector and creates one document per paper,
rendered as Markdown. Deduplication uses a stable hash ``arxiv:{entry_id}``.
"""

from __future__ import annotations

import logging
from datetime import date, datetime
from typing import Any

from alfred.connectors.arxiv_connector import ArxivConnector
from alfred.schemas.documents import DocumentIngest
from alfred.services.doc_storage_pg import DocStorageService

logger = logging.getLogger(__name__)


def _render_paper_markdown(metadata: dict[str, Any], content: str) -> str:
    """Render an ArXiv paper as Markdown."""
    title = metadata.get("Title") or "Untitled"
    authors = metadata.get("Authors") or "Unknown"
    summary = metadata.get("Summary") or ""
    published = metadata.get("Published") or ""

    lines = [
        f"# {title}",
        "",
        f"**Authors:** {authors}",
    ]

    if published:
        lines.append(f"**Published:** {published}")

    entry_id = metadata.get("entry_id") or ""
    if entry_id:
        lines.append(f"**ArXiv:** {entry_id}")

    pdf_url = metadata.get("pdf_url") or ""
    if pdf_url:
        lines.append(f"**PDF:** {pdf_url}")

    lines.append("")

    if summary:
        lines.extend([
            "## Abstract",
            "",
            summary.strip(),
            "",
        ])

    if content and content.strip():
        lines.extend([
            "## Content",
            "",
            content.strip(),
        ])

    return "\n".join(lines)


def import_arxiv(
    *,
    doc_store: DocStorageService,
    query: str,
    categories: list[str] | None = None,
    date_from: str | date | datetime | None = None,
    date_to: str | date | datetime | None = None,
    max_results: int = 10,
) -> dict[str, Any]:
    """Import ArXiv papers into Alfred's document store.

    Args:
        doc_store: The document storage service.
        query: Search query for ArXiv.
        categories: Optional list of ArXiv categories to filter (e.g. ["cs.AI"]).
        date_from: Optional start date for filtering.
        date_to: Optional end date for filtering.
        max_results: Maximum number of papers to import (default 10).
    """
    connector = ArxivConnector(
        load_max_docs=max_results,
        doc_content_chars_max=40000,
    )

    try:
        docs = connector.search(
            query,
            categories=categories,
            date_from=date_from,
            date_to=date_to,
            max_results=max_results,
        )
    except Exception as exc:
        logger.exception("ArXiv search failed for query: %s", query)
        return {
            "ok": False,
            "created": 0,
            "updated": 0,
            "skipped": 0,
            "errors": [{"error": str(exc)}],
            "documents": [],
        }

    created = 0
    updated = 0
    skipped = 0
    errors: list[dict[str, str]] = []
    documents: list[dict[str, str]] = []

    for doc in docs:
        metadata = doc.metadata or {}
        entry_id = metadata.get("entry_id") or ""

        if not entry_id:
            skipped += 1
            continue

        try:
            title = metadata.get("Title") or "Untitled"
            content = doc.page_content or ""
            markdown = _render_paper_markdown(metadata, content)
            cleaned_text = markdown.strip()

            source_url = entry_id or metadata.get("pdf_url") or f"arxiv://{entry_id}"
            stable_hash = f"arxiv:{entry_id}"

            # Extract categories as tags
            categories_str = metadata.get("Categories") or ""
            tag_names = [c.strip() for c in categories_str.split() if c.strip()] if categories_str else []

            arxiv_meta: dict[str, Any] = {
                "entry_id": entry_id,
                "title": title,
                "authors": metadata.get("Authors"),
                "summary": metadata.get("Summary"),
                "published": metadata.get("Published"),
                "updated": metadata.get("Updated"),
                "pdf_url": metadata.get("pdf_url"),
                "categories": categories_str,
                "primary_category": metadata.get("Primary Category"),
                "links": metadata.get("Links"),
            }

            ingest = DocumentIngest(
                source_url=source_url,
                title=title,
                content_type="arxiv_paper",
                raw_markdown=markdown,
                cleaned_text=cleaned_text,
                hash=stable_hash,
                tags=tag_names or None,
                metadata={"source": "arxiv", "arxiv": arxiv_meta},
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
                    metadata_update={"source": "arxiv", "arxiv": arxiv_meta},
                )
            else:
                created += 1

            documents.append({"entry_id": entry_id, "document_id": doc_id})

        except Exception as exc:
            logger.exception("ArXiv import failed for paper %s", entry_id)
            errors.append({"entry_id": str(entry_id), "error": str(exc)})

    return {
        "ok": True,
        "created": created,
        "updated": updated,
        "skipped": skipped,
        "errors": errors,
        "documents": documents,
    }


__all__ = ["import_arxiv"]
