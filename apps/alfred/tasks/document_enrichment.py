from __future__ import annotations

import logging

from celery import shared_task

from alfred.core.dependencies import get_doc_storage_service

logger = logging.getLogger(__name__)


def _auto_link_zettels(card_ids: list[str], session) -> dict:
    """Run suggest_links on each card and auto-create links for high-confidence matches.

    For each newly created zettel, generates an embedding (if missing), finds
    similar cards via composite scoring, and creates bidirectional links:
    - confidence >= 0.8: auto-linked as "auto_high" type
    - confidence 0.6-0.8: auto-linked as "auto_suggested" type

    This is best-effort: failures are logged but never block the pipeline.

    Returns a summary dict with counts of links created and errors.
    """
    from alfred.services.zettelkasten_service import ZettelkastenService

    zk = ZettelkastenService(session=session)
    stats = {"links_created": 0, "cards_processed": 0, "errors": 0}

    for card_id_str in card_ids:
        try:
            card_id = int(card_id_str)
            card = zk.get_card(card_id)
            if not card:
                logger.warning("Auto-link: card %s not found, skipping", card_id_str)
                continue

            # Ensure the card has an embedding before suggesting links
            try:
                card = zk.ensure_embedding(card)
            except Exception:
                logger.warning(
                    "Auto-link: failed to embed card %s, skipping link suggestions",
                    card_id,
                    exc_info=True,
                )
                stats["errors"] += 1
                continue

            suggestions = zk.suggest_links(card_id, min_confidence=0.6, limit=5)
            stats["cards_processed"] += 1

            for suggestion in suggestions:
                score = suggestion.scores.composite_score
                confidence_level = suggestion.scores.confidence

                # Choose link type based on confidence
                if confidence_level == "high":
                    link_type = "auto_high"
                else:
                    link_type = "auto_suggested"

                try:
                    zk.create_link(
                        from_card_id=card_id,
                        to_card_id=suggestion.to_card_id,
                        type=link_type,
                        context=suggestion.reason,
                        bidirectional=True,
                    )
                    stats["links_created"] += 1
                    logger.info(
                        "Auto-linked card %d -> %d (score=%.3f, confidence=%s, type=%s)",
                        card_id,
                        suggestion.to_card_id,
                        score,
                        confidence_level,
                        link_type,
                    )
                except Exception:
                    logger.warning(
                        "Auto-link: failed to create link %d -> %d",
                        card_id,
                        suggestion.to_card_id,
                        exc_info=True,
                    )
                    stats["errors"] += 1

        except Exception:
            logger.warning(
                "Auto-link: unexpected error processing card %s",
                card_id_str,
                exc_info=True,
            )
            stats["errors"] += 1

    logger.info(
        "Auto-link complete: %d cards processed, %d links created, %d errors",
        stats["cards_processed"],
        stats["links_created"],
        stats["errors"],
    )
    return stats


def _create_zettel_from_enrichment(doc_id: str) -> str | None:
    """Create multiple atomic zettel cards from an enriched document using LLM decomposition.

    This is the bridge between the Inbox (documents) and the Knowledge Hub (zettels).
    Each enriched document is decomposed into 2-10 atomic zettels (one per key concept).
    Each zettel links back to the source document via document_id.

    Auto-created cards get status='draft' so they don't enter the spaced repetition
    queue until the user reviews and activates them.

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

    session = next(get_db_session())
    try:
        zk = ZettelkastenService(session=session)

        # Only skip if auto-created (draft) cards already exist for this document.
        # Manual cards (status='active') should NOT suppress auto-decomposition.
        existing = zk.list_cards(document_id=doc_id, limit=100)
        auto_created = [c for c in existing if c.status == "draft"]
        if auto_created:
            logger.info("Auto-created zettels already exist for document %s (count: %d)", doc_id, len(auto_created))
            return ",".join(str(card.id) for card in auto_created)

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

        created_ids: list[str] = []

        # Check if we have enough content for LLM decomposition
        can_decompose = bool(cleaned_text and short_summary)

        if can_decompose:
            try:
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

                raw = response.content if hasattr(response, "content") else str(response)
                card_dicts = parse_decomposition_response(raw)

                if card_dicts:
                    for card_dict in card_dicts:
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
                            status="draft",
                        )
                        created_ids.append(str(card.id))
                        logger.info("Created draft zettel %s from document %s", card.id, doc_id)
                else:
                    logger.warning("LLM decomposition returned no cards for document %s", doc_id)
                    can_decompose = False  # fall through to fallback

            except Exception as exc:
                logger.warning("LLM decomposition failed for %s: %s", doc_id, exc)
                can_decompose = False  # fall through to fallback

        # Fallback: create single zettel from summary
        if not created_ids and short_summary:
            if not can_decompose:
                logger.info("Falling back to single card for document %s", doc_id)
            card = zk.create_card(
                title=title,
                content=short_summary,
                tags=final_tags,
                topic=final_topic,
                source_url=source_url,
                document_id=doc_id,
                importance=5,
                confidence=0.7,
                status="draft",
            )
            created_ids.append(str(card.id))
            logger.info("Created fallback draft zettel %s from document %s", card.id, doc_id)

        # Auto-link newly created zettels to existing knowledge graph
        if created_ids:
            try:
                link_stats = _auto_link_zettels(created_ids, session)
                if link_stats["links_created"] > 0:
                    logger.info(
                        "Auto-linked %d connections for document %s zettels",
                        link_stats["links_created"],
                        doc_id,
                    )
            except Exception:
                logger.warning(
                    "Auto-linking failed for document %s zettels, continuing",
                    doc_id,
                    exc_info=True,
                )

        return ",".join(created_ids) if created_ids else None

    except Exception:
        logger.exception("Failed to create zettels from document %s", doc_id)
        return None
    finally:
        session.close()


@shared_task(name="alfred.tasks.document_enrichment.enrich", bind=True)
def document_enrichment_task(self, *, doc_id: str, force: bool = False) -> dict:
    """Enrich an existing stored document (LLM + optional graph).

    After enrichment, automatically creates a zettel card in the Knowledge Hub
    from the document's summary and topics. This bridges Inbox -> Knowledge.

    On success the document's ``pipeline_status`` is set to ``'complete'``.
    """
    svc = get_doc_storage_service()
    logger.info("Running document enrichment task (force=%s) for %s", force, doc_id)

    self.update_state(state="PROGRESS", meta={"pipeline_step": "Enriching", "doc_id": doc_id})
    result = svc.enrich_document(doc_id, force=force)

    # Bridge: create zettel from enrichment
    if not result.get("skipped"):
        self.update_state(state="PROGRESS", meta={"pipeline_step": "Creating zettels", "doc_id": doc_id})
        zettel_id = _create_zettel_from_enrichment(doc_id)
        if zettel_id:
            result["zettel_id"] = zettel_id

    # Mark document as fully processed
    self.update_state(state="PROGRESS", meta={"pipeline_step": "Finalizing", "doc_id": doc_id})
    try:
        from alfred.tasks.document_pipeline import _set_pipeline_status

        _set_pipeline_status(doc_id, "complete")
    except Exception:
        logger.warning("Failed to set pipeline_status=complete for %s", doc_id, exc_info=True)

    return result
