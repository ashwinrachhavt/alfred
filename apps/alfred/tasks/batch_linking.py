"""Batch link generation tasks.

Single-card task: runs suggest_links for one card and auto-creates
high-confidence links.

Batch coordinator: finds cards with few links and enqueues individual
link tasks for parallel execution.
"""
from __future__ import annotations

import logging

from celery import shared_task
from sqlmodel import select

from alfred.core.database import SessionLocal
from alfred.models.zettel import ZettelCard, ZettelLink
from alfred.services.zettelkasten_service import ZettelkastenService

logger = logging.getLogger(__name__)

AUTO_LINK_THRESHOLD = 0.75  # Only auto-create links above this score


@shared_task(name="alfred.tasks.batch_linking.link_card")
def link_card_task(*, card_id: int, min_confidence: float = 0.6, auto_link: bool = True) -> dict:
    """Run suggest_links for a single card and optionally auto-create high-confidence links."""
    session = SessionLocal()
    try:
        svc = ZettelkastenService(session)
        card = svc.get_card(card_id)
        if not card:
            return {"ok": False, "error": "Card not found", "card_id": card_id}

        try:
            suggestions = svc.suggest_links(
                card_id=card_id, min_confidence=min_confidence, limit=10
            )
        except Exception as exc:
            logger.warning("suggest_links failed for card %d: %s", card_id, exc)
            return {"ok": False, "error": str(exc), "card_id": card_id}

        created_links: list[dict] = []
        if auto_link:
            for suggestion in suggestions:
                if suggestion.scores.composite_score >= AUTO_LINK_THRESHOLD:
                    try:
                        svc.create_link(
                            from_card_id=card_id,
                            to_card_id=suggestion.to_card_id,
                            type="ai-suggested",
                            context=suggestion.reason,
                            bidirectional=True,
                        )
                        created_links.append({
                            "to_card_id": suggestion.to_card_id,
                            "score": suggestion.scores.composite_score,
                            "reason": suggestion.reason,
                        })
                    except Exception as exc:
                        # Link may already exist (unique constraint)
                        logger.debug("Link creation skipped for %d->%d: %s",
                                     card_id, suggestion.to_card_id, exc)

        return {
            "ok": True,
            "card_id": card_id,
            "suggestions_found": len(suggestions),
            "links_created": len(created_links),
            "created": created_links,
        }
    finally:
        session.close()


@shared_task(name="alfred.tasks.batch_linking.batch_link")
def batch_link_task(
    *,
    limit: int = 50,
    max_existing_links: int = 3,
    min_confidence: float = 0.6,
    auto_link: bool = True,
    enqueue_only: bool = True,
) -> dict:
    """Find cards with few links and queue link generation for each.

    Args:
        limit: Max cards to process
        max_existing_links: Only process cards with this many or fewer existing links
        min_confidence: Minimum confidence for suggestions
        auto_link: Auto-create links above AUTO_LINK_THRESHOLD
        enqueue_only: If True, enqueue individual tasks (parallel). If False, run inline.
    """
    session = SessionLocal()
    try:
        # Find cards with few links (candidates for link discovery)
        all_cards = list(session.exec(
            select(ZettelCard)
            .where(ZettelCard.status != "archived")
            .order_by(ZettelCard.updated_at.desc())
        ))

        # Count existing links per card
        all_links = list(session.exec(select(ZettelLink)))
        link_counts: dict[int, int] = {}
        for link in all_links:
            link_counts[link.from_card_id] = link_counts.get(link.from_card_id, 0) + 1
            link_counts[link.to_card_id] = link_counts.get(link.to_card_id, 0) + 1

        # Filter to cards needing links
        candidates = [
            c for c in all_cards
            if link_counts.get(c.id or 0, 0) <= max_existing_links
        ][:limit]

        card_ids = [int(c.id or 0) for c in candidates if (c.id or 0) > 0]
        if not card_ids:
            return {"ok": True, "queued": 0, "card_ids": []}

        if enqueue_only:
            task_ids: list[str] = []
            for cid in card_ids:
                async_result = link_card_task.delay(
                    card_id=cid,
                    min_confidence=min_confidence,
                    auto_link=auto_link,
                )
                task_ids.append(async_result.id)
            return {
                "ok": True,
                "queued": len(task_ids),
                "card_ids": card_ids,
                "task_ids": task_ids,
            }

        # Inline mode (for testing)
        results = []
        for cid in card_ids:
            result = link_card_task(card_id=cid, min_confidence=min_confidence, auto_link=auto_link)
            results.append(result)
        total_created = sum(r.get("links_created", 0) for r in results)
        return {
            "ok": True,
            "processed": len(results),
            "card_ids": card_ids,
            "total_links_created": total_created,
        }
    finally:
        session.close()
