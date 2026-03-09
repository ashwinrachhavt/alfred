"""Ingest Hypothes.is annotations into Alfred's document store.

Each annotation becomes a single document, rendered as Markdown with
the quoted text, user note, and tags. Annotations are grouped by URI
in the metadata for context.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from typing import Any

from alfred.connectors.hypothesis_connector import HypothesisClient
from alfred.schemas.documents import DocumentIngest
from alfred.schemas.imports import CONTENT_TYPE_HYPOTHESIS_ANNOTATION, ImportStats
from alfred.services.doc_storage_pg import DocStorageService

logger = logging.getLogger(__name__)


def _extract_quote(annotation: dict[str, Any]) -> str | None:
    """Extract the highlighted quote from the annotation's target selectors."""
    targets = annotation.get("target") or []
    for target in targets:
        selectors = target.get("selector") or []
        for selector in selectors:
            if selector.get("type") == "TextQuoteSelector":
                exact = (selector.get("exact") or "").strip()
                if exact:
                    return exact
    return None


def _render_annotation_markdown(
    annotation: dict[str, Any],
    quote: str | None,
) -> str:
    """Render a Hypothes.is annotation as Markdown."""
    doc_title = ""
    document = annotation.get("document") or {}
    titles = document.get("title") or []
    if titles:
        doc_title = titles[0]

    uri = annotation.get("uri") or ""
    tags = annotation.get("tags") or []
    note = (annotation.get("text") or "").strip()
    created = annotation.get("created") or ""

    lines = []

    # Header
    title_str = doc_title or uri or "Annotation"
    lines.append(f"# {title_str}")

    meta_parts: list[str] = []
    if uri:
        meta_parts.append(f"**Source:** {uri}")
    if created:
        meta_parts.append(f"**Created:** {created}")
    if meta_parts:
        lines.append("  ".join(meta_parts))
    lines.append("")

    # Quote
    if quote:
        lines.append("> " + quote.replace("\n", "\n> "))
        lines.append("")

    # Note
    if note:
        lines.append(note)
        lines.append("")

    # Tags
    if tags:
        lines.append(f"*Tags: {', '.join(tags)}*")

    return "\n".join(lines)


def import_hypothesis(
    *,
    doc_store: DocStorageService,
    token: str | None = None,
    limit: int | None = None,
) -> dict[str, Any]:
    """Import annotations from Hypothes.is into the document store.

    Args:
        doc_store: The document storage service.
        token: Optional explicit Hypothes.is API token.
        limit: Max number of annotations to import.

    Returns:
        Summary dict with ok, created, updated, skipped, errors, documents.
    """
    client = HypothesisClient(token=token)

    # Get user profile to filter by user
    try:
        profile = client.get_user_profile()
        userid = profile.get("userid")
    except Exception:
        logger.warning("Could not fetch Hypothesis user profile; fetching without user filter")
        userid = None

    annotations = client.search_all(user=userid)

    if limit is not None:
        annotations = annotations[:limit]

    # Group annotations by URI for metadata context
    by_uri: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for ann in annotations:
        uri = ann.get("uri", "unknown")
        by_uri[uri].append(ann)

    stats = ImportStats()

    for annotation in annotations:
        annotation_id = annotation.get("id")
        if not annotation_id:
            stats.skipped += 1
            continue

        uri = annotation.get("uri")
        if not uri:
            stats.skipped += 1
            continue

        try:
            quote = _extract_quote(annotation)
            note = (annotation.get("text") or "").strip()

            # Skip annotations with neither quote nor note
            if not quote and not note:
                stats.skipped += 1
                continue

            markdown = _render_annotation_markdown(annotation, quote)
            cleaned_text = markdown.strip()

            if not cleaned_text:
                stats.skipped += 1
                continue

            # Title from the annotated document
            doc_info = annotation.get("document") or {}
            doc_titles = doc_info.get("title") or []
            title = doc_titles[0] if doc_titles else uri

            stable_hash = f"hypothesis:{annotation_id}"
            tags = annotation.get("tags") or []

            # Count sibling annotations on the same URI
            siblings_on_uri = len(by_uri.get(uri, []))

            hypothesis_meta: dict[str, Any] = {
                "annotation_id": annotation_id,
                "uri": uri,
                "created": annotation.get("created"),
                "updated": annotation.get("updated"),
                "user": annotation.get("user"),
                "group": annotation.get("group"),
                "has_quote": bool(quote),
                "has_note": bool(note),
                "annotations_on_page": siblings_on_uri,
            }

            ingest = DocumentIngest(
                source_url=uri,
                title=title,
                content_type=CONTENT_TYPE_HYPOTHESIS_ANNOTATION,
                raw_markdown=markdown,
                cleaned_text=cleaned_text,
                hash=stable_hash,
                tags=tags or None,
                metadata={"source": "hypothesis", "hypothesis": hypothesis_meta},
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
                        metadata_update={"source": "hypothesis", "hypothesis": hypothesis_meta},
                    )
                    stats.updated += 1
                except Exception:
                    logger.debug("Skipping update for duplicate %s", doc_id)
                    stats.skipped += 1
            else:
                stats.created += 1

            stats.documents.append({"annotation_id": annotation_id, "document_id": doc_id})

        except Exception as exc:
            logger.exception("Hypothesis import failed for annotation %s", annotation_id)
            stats.errors.append({"annotation_id": str(annotation_id), "error": str(exc)})

    return stats.to_dict()


__all__ = ["import_hypothesis"]
