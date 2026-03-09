"""Ingest Semantic Scholar papers into Alfred's document store.

Each paper becomes a single document with its metadata, abstract, and TLDR
rendered as Markdown. Supports search-based discovery and import.
"""

from __future__ import annotations

import logging
from typing import Any

from alfred.connectors.semantic_scholar_connector import SemanticScholarClient
from alfred.schemas.documents import DocumentIngest
from alfred.schemas.imports import CONTENT_TYPE_ACADEMIC_PAPER, ImportStats
from alfred.services.doc_storage_pg import DocStorageService

logger = logging.getLogger(__name__)


def _render_paper_markdown(paper: dict[str, Any]) -> str:
    """Render a Semantic Scholar paper as Markdown."""
    title = paper.get("title") or "Untitled"
    year = paper.get("year")
    citation_count = paper.get("citationCount", 0)

    authors = paper.get("authors") or []
    author_names = ", ".join(a.get("name", "Unknown") for a in authors) or "Unknown"

    lines = [
        f"# {title}",
        "",
        f"**Authors:** {author_names}",
    ]

    if year:
        lines.append(f"**Year:** {year}")
    lines.append(f"**Citations:** {citation_count}")

    pub_date = paper.get("publicationDate")
    if pub_date:
        lines.append(f"**Published:** {pub_date}")

    fields = paper.get("fieldsOfStudy") or []
    if fields:
        lines.append(f"**Fields:** {', '.join(fields)}")

    lines.append("")

    # TLDR
    tldr = paper.get("tldr")
    if tldr:
        tldr_text = tldr.get("text") if isinstance(tldr, dict) else str(tldr)
        if tldr_text:
            lines.extend(["## TL;DR", "", f"> {tldr_text}", ""])

    # Abstract
    abstract = (paper.get("abstract") or "").strip()
    if abstract:
        lines.extend(["## Abstract", "", abstract, ""])

    # Open Access PDF
    oa_pdf = paper.get("openAccessPdf")
    if oa_pdf:
        pdf_url = oa_pdf.get("url") if isinstance(oa_pdf, dict) else str(oa_pdf)
        if pdf_url:
            lines.extend([f"**Open Access PDF:** {pdf_url}", ""])

    return "\n".join(lines)


def import_semantic_scholar(
    *,
    doc_store: DocStorageService,
    query: str,
    api_key: str | None = None,
    limit: int = 10,
    year: str | None = None,
) -> dict[str, Any]:
    """Search for and import Semantic Scholar papers into Alfred's document store.

    Args:
        doc_store: The document storage service.
        query: Search query string for finding papers.
        api_key: Optional Semantic Scholar API key (free tier works without one).
        limit: Maximum number of papers to import (default 10).
        year: Optional year or year range filter (e.g., "2020", "2019-2023").
    """
    client = SemanticScholarClient(api_key=api_key)

    if year:
        papers = client.search_by_keyword(query, year=year, limit=limit)
    else:
        papers = client.search_papers(query, limit=limit)

    # Fetch full details (including TLDR) for each paper
    detailed_papers: list[dict[str, Any]] = []
    for paper in papers:
        paper_id = paper.get("paperId")
        if not paper_id:
            continue
        try:
            detail = client.get_paper(paper_id)
            detailed_papers.append(detail)
        except Exception:
            # Fall back to search-result data if detail fetch fails
            logger.warning("Failed to fetch details for paper %s, using search data", paper_id)
            detailed_papers.append(paper)

    stats = ImportStats()

    for paper in detailed_papers:
        paper_id = paper.get("paperId")
        if not paper_id:
            stats.skipped += 1
            continue

        try:
            title = paper.get("title") or "Untitled"
            markdown = _render_paper_markdown(paper)
            cleaned_text = markdown.strip()

            source_url = paper.get("url") or f"https://www.semanticscholar.org/paper/{paper_id}"
            stable_hash = f"s2:{paper_id}"

            fields_of_study = paper.get("fieldsOfStudy") or []

            authors = paper.get("authors") or []
            author_list = [
                {"id": a.get("authorId"), "name": a.get("name")}
                for a in authors
            ]

            s2_meta = {
                "paper_id": paper_id,
                "year": paper.get("year"),
                "citation_count": paper.get("citationCount"),
                "publication_date": paper.get("publicationDate"),
                "authors": author_list,
                "fields_of_study": fields_of_study,
            }

            oa_pdf = paper.get("openAccessPdf")
            if oa_pdf and isinstance(oa_pdf, dict):
                s2_meta["open_access_pdf_url"] = oa_pdf.get("url")

            ingest = DocumentIngest(
                source_url=source_url,
                title=title,
                content_type=CONTENT_TYPE_ACADEMIC_PAPER,
                raw_markdown=markdown,
                cleaned_text=cleaned_text,
                hash=stable_hash,
                tags=fields_of_study or None,
                metadata={"source": "semantic_scholar", "semantic_scholar": s2_meta},
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
                        metadata_update={"source": "semantic_scholar", "semantic_scholar": s2_meta},
                    )
                    stats.updated += 1
                except Exception:
                    logger.debug("Skipping update for duplicate %s", doc_id)
                    stats.skipped += 1
            else:
                stats.created += 1

            stats.documents.append({"paper_id": paper_id, "document_id": doc_id})

        except Exception as exc:
            logger.exception("Semantic Scholar import failed for paper %s", paper_id)
            stats.errors.append({"paper_id": str(paper_id), "error": str(exc)})

    return stats.to_dict()


__all__ = ["import_semantic_scholar"]
