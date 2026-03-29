from __future__ import annotations

import logging

from celery import shared_task

from alfred.core.dependencies import get_doc_storage_service

logger = logging.getLogger(__name__)


def _create_zettel_from_enrichment(doc_id: str) -> str | None:
    """Create multiple atomic zettel cards from an enriched document using LLM decomposition.

    This is the bridge between the Inbox (documents) and the Knowledge Hub (zettels).
    Each enriched document is decomposed into 2-10 atomic zettels (one per key concept).
    Each zettel links back to the source document via document_id.

    Returns comma-separated zettel card IDs if created, None if skipped.
    """
    from alfred.api.dependencies import get_db_session
    from alfred.core.llm_factory import get_chat_model
    from alfred.services.zettel_decomposer import (
        build_decomposition_prompt,
        parse_decomposition_response,
    )
    from alfred.services.zettelkasten_service import ZettelkastenService

    svc = get_doc_storage_service()
    doc = svc.get_document_details(doc_id)
    if not doc:
        return None

    # Check if zettels already exist for this document (skip if so)
    session = next(get_db_session())
    try:
        zk = ZettelkastenService(session=session)
        existing = zk.list_cards(document_id=doc_id, limit=100)
        if existing:
            logger.info("Zettels already exist for document %s (count: %d)", doc_id, len(existing))
            return ",".join(str(card.id) for card in existing)

        # Gather document context
        title = doc.get("title") or "Untitled"
        source_url = doc.get("source_url")
        cleaned_text = doc.get("cleaned_text", "")
        summary = doc.get("summary") or {}
        short_summary = summary.get("short", "").strip() if isinstance(summary, dict) else ""
        topics = doc.get("topics") or {}
        primary_topic = topics.get("primary") if isinstance(topics, dict) else None
        tags = doc.get("tags") or []

        # Prefer taxonomy classification over raw extraction topics
        classification = doc.get("classification") or {}
        domain = classification.get("domain", {})
        subdomain = classification.get("subdomain", {})

        if domain.get("slug"):
            classified_topic = domain.get("slug")
            classified_tags = [t for t in [
                domain.get("slug"),
                subdomain.get("slug"),
                *[mt.get("slug", "") for mt in (classification.get("microtopics") or [])[:3]],
            ] if t]
        else:
            classified_topic = None
            classified_tags = []

        final_topic = classified_topic or primary_topic
        final_tags = list(set(
            classified_tags
            + ([primary_topic] if primary_topic else [])
            + (tags[:2] if tags else [])
        ))

        # Try LLM decomposition
        created_ids = []
        try:
            if not cleaned_text or not short_summary:
                logger.info("Skipping decomposition for %s — no cleaned_text or summary", doc_id)
                raise ValueError("No content to decompose")

            # Build prompt and call LLM
            prompt = build_decomposition_prompt(
                title=title,
                summary=short_summary,
                cleaned_text=cleaned_text,
                topics=topics,
            )

            llm = get_chat_model()
            response = llm.invoke([
                {"role": "system", "content": "You are a knowledge card generator. Return only valid JSON."},
                {"role": "user", "content": prompt},
            ])

            # Parse response
            raw = response.content if hasattr(response, "content") else str(response)
            card_dicts = parse_decomposition_response(raw)

            if not card_dicts:
                logger.warning("LLM decomposition returned no cards for document %s", doc_id)
                raise ValueError("No cards from decomposition")

            # Create each card
            for card_dict in card_dicts:
                # Merge document tags with card-specific tags
                card_tags = list(set(final_tags + card_dict.get("tags", [])))

                card = zk.create_card(
                    title=card_dict["title"],
                    content=card_dict["content"],
                    tags=card_tags,
                    topic=final_topic,
                    source_url=source_url,
                    document_id=doc_id,
                    importance=5,
                    confidence=0.7,
                    status="active",
                )
                created_ids.append(str(card.id))
                logger.info("Created zettel %s from document %s", card.id, doc_id)

        except Exception as exc:
            # Fallback: create single zettel from summary
            logger.warning("LLM decomposition failed for %s: %s — falling back to single card", doc_id, exc)

            if not short_summary:
                logger.info("Skipping fallback zettel creation for %s — no summary", doc_id)
                return None

            card = zk.create_card(
                title=title,
                content=short_summary,
                tags=final_tags,
                topic=final_topic,
                source_url=source_url,
                document_id=doc_id,
                importance=5,
                confidence=0.7,
                status="active",
            )
            created_ids.append(str(card.id))
            logger.info("Created fallback zettel %s from document %s", card.id, doc_id)

        return ",".join(created_ids) if created_ids else None

    except Exception:
        logger.exception("Failed to create zettels from document %s", doc_id)
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
