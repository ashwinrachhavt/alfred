from __future__ import annotations

import logging
from datetime import UTC

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


def _push_zettel_notifications(
    card_ids: list[str],
    link_stats: dict,
    source_title: str,
    tags: list[str],
    topic: str | None,
    session,
) -> None:
    """Check if newly created zettels match recent agent threads and push notifications.

    Matching is lightweight (topic/tag overlap only, no semantic search).
    Best-effort: failures are logged but never block the pipeline.
    """
    from datetime import datetime, timedelta

    from sqlmodel import select

    from alfred.models.thinking import AgentMessageRow, ThinkingSessionRow
    from alfred.services.knowledge_notifications import push_knowledge_notification
    from alfred.services.zettelkasten_service import ZettelkastenService

    zk = ZettelkastenService(session=session)

    # Find recent agent threads (last 7 days)
    cutoff = datetime.now(UTC) - timedelta(days=7)
    recent_threads = session.exec(
        select(ThinkingSessionRow)
        .where(ThinkingSessionRow.session_type == "agent")
        .where(ThinkingSessionRow.updated_at >= cutoff)
        .limit(50)
    ).all()

    if not recent_threads:
        return

    # Build a quick lookup of thread topics and tags
    thread_infos: list[dict] = []
    for thread in recent_threads:
        thread_tags: set[str] = set()
        thread_topic = (thread.topic or "").lower().strip()

        # Collect tags from thread itself
        if thread.tags:
            thread_tags.update(t.lower() for t in thread.tags if isinstance(t, str))

        # Collect tags from related_cards in recent messages
        try:
            recent_msgs = session.exec(
                select(AgentMessageRow)
                .where(AgentMessageRow.thread_id == thread.id)
                .order_by(AgentMessageRow.created_at.desc())
                .limit(10)
            ).all()
            for msg in recent_msgs:
                if msg.related_cards:
                    for rc in msg.related_cards:
                        if isinstance(rc, dict) and rc.get("tags"):
                            thread_tags.update(t.lower() for t in rc["tags"] if isinstance(t, str))
        except Exception:
            pass  # Skip message scanning on error

        thread_infos.append(
            {
                "id": thread.id,
                "title": thread.title or "Untitled thread",
                "topic": thread_topic,
                "tags": thread_tags,
            }
        )

    tag_set = {t.lower() for t in tags if isinstance(t, str)}
    topic_lower = (topic or "").lower().strip()

    for card_id_str in card_ids:
        try:
            card = zk.get_card(int(card_id_str))
            if not card:
                continue

            # Find matching threads via topic or tag overlap
            matches: list[dict] = []
            for ti in thread_infos:
                reason = None
                if topic_lower and ti["topic"] and topic_lower in ti["topic"]:
                    reason = "topic overlap"
                elif ti["topic"] and topic_lower and ti["topic"] in topic_lower:
                    reason = "topic overlap"
                elif tag_set & ti["tags"]:
                    overlapping = tag_set & ti["tags"]
                    reason = f"shared tags: {', '.join(list(overlapping)[:3])}"

                if reason:
                    matches.append(
                        {
                            "thread_id": ti["id"],
                            "title": ti["title"],
                            "reason": reason,
                        }
                    )

            if not matches:
                continue

            notification = {
                "type": "new_knowledge",
                "zettel_id": card.id,
                "zettel_title": card.title or "Untitled",
                "linked_to": [],
                "source_document": source_title,
                "thread_matches": matches[:5],
            }

            # Include link info from auto-linking stats if available
            if link_stats.get("links_created", 0) > 0:
                notification["linked_to_count"] = link_stats["links_created"]

            push_knowledge_notification(notification)
            logger.info(
                "Pushed knowledge notification for zettel %s (matched %d threads)",
                card_id_str,
                len(matches),
            )
        except Exception:
            logger.warning(
                "Failed to push notification for card %s",
                card_id_str,
                exc_info=True,
            )


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
            logger.info(
                "Auto-created zettels already exist for document %s (count: %d)",
                doc_id,
                len(auto_created),
            )
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
            classified_tags = [
                t
                for t in [
                    domain.get("slug"),
                    subdomain.get("slug"),
                    *[mt.get("slug", "") for mt in (classification.get("microtopics") or [])[:3]],
                ]
                if t
            ]
        else:
            classified_topic = None
            classified_tags = []

        final_topic = classified_topic or primary_topic
        final_tags = list(
            set(
                classified_tags
                + ([primary_topic] if primary_topic else [])
                + (tags[:2] if tags else [])
            )
        )

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
                response = llm.invoke(
                    [
                        {
                            "role": "system",
                            "content": "You are a knowledge card generator. Return only valid JSON.",
                        },
                        {"role": "user", "content": prompt},
                    ]
                )

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
        link_stats: dict = {"links_created": 0}
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

            # Push knowledge notifications for new zettels that match agent threads
            try:
                _push_zettel_notifications(
                    created_ids, link_stats, title, final_tags, final_topic, session
                )
            except Exception:
                logger.warning(
                    "Knowledge notification push failed for document %s, continuing",
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
        self.update_state(
            state="PROGRESS", meta={"pipeline_step": "Creating zettels", "doc_id": doc_id}
        )
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
