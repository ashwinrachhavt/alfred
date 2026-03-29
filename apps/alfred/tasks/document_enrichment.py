from __future__ import annotations

import logging

from celery import shared_task

from alfred.core.dependencies import get_doc_storage_service

logger = logging.getLogger(__name__)


def _create_zettel_from_enrichment(doc_id: str) -> str | None:
    """Create a zettel card from an enriched document's summary and topics.

    This is the bridge between the Inbox (documents) and the Knowledge Hub (zettels).
    Each enriched document produces one atomic zettel with its short summary as content.
    The zettel links back to the source document via document_id.

    Returns the zettel card ID if created, None if skipped.
    """
    from alfred.api.dependencies import get_db_session
    from alfred.services.zettelkasten_service import ZettelkastenService

    svc = get_doc_storage_service()
    doc = svc.get_document_details(doc_id)
    if not doc:
        return None

    # Skip if no enrichment/summary — nothing to create a zettel from
    summary = doc.get("summary") or {}
    short_summary = summary.get("short", "").strip() if isinstance(summary, dict) else ""
    if not short_summary:
        logger.info("Skipping zettel creation for %s — no summary", doc_id)
        return None

    title = doc.get("title") or "Untitled"
    source_url = doc.get("source_url")
    topics = doc.get("topics") or {}
    primary_topic = topics.get("primary") if isinstance(topics, dict) else None
    secondary_topics = topics.get("secondary", []) if isinstance(topics, dict) else []
    tags = doc.get("tags") or []

    # Combine topic tags
    all_tags = list(set(
        ([primary_topic] if primary_topic else [])
        + (secondary_topics[:5] if secondary_topics else [])
        + (tags[:3] if tags else [])
    ))

    # Check if a zettel already exists for this document
    session = next(get_db_session())
    try:
        zk = ZettelkastenService(session=session)
        existing = zk.list_cards(q=None, topic=None, limit=1000)
        for card in existing:
            if getattr(card, "document_id", None) == doc_id:
                logger.info("Zettel already exists for document %s", doc_id)
                return str(card.id)

        card = zk.create_card(
            title=title,
            content=short_summary,
            tags=all_tags,
            topic=primary_topic,
            source_url=source_url,
            document_id=doc_id,
            importance=5,
            confidence=0.7,
            status="active",
        )
        logger.info("Created zettel %s from document %s", card.id, doc_id)
        return str(card.id)
    except Exception:
        logger.exception("Failed to create zettel from document %s", doc_id)
        return None
    finally:
        session.close()


@shared_task(name="alfred.tasks.document_enrichment.enrich")
def document_enrichment_task(*, doc_id: str, force: bool = False) -> dict:
    """Enrich an existing stored document (LLM + optional graph).

    After enrichment, automatically creates a zettel card in the Knowledge Hub
    from the document's summary and topics. This bridges Inbox -> Knowledge.

    On success the document's ``pipeline_status`` is set to ``'complete'``.
    """
    svc = get_doc_storage_service()
    logger.info("Running document enrichment task (force=%s) for %s", force, doc_id)
    result = svc.enrich_document(doc_id, force=force)

    # Bridge: create zettel from enrichment
    if not result.get("skipped"):
        zettel_id = _create_zettel_from_enrichment(doc_id)
        if zettel_id:
            result["zettel_id"] = zettel_id

    # Mark document as fully processed
    try:
        from alfred.tasks.document_pipeline import _set_pipeline_status

        _set_pipeline_status(doc_id, "complete")
    except Exception:
        logger.warning("Failed to set pipeline_status=complete for %s", doc_id, exc_info=True)

    return result
