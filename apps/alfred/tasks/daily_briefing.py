"""Daily briefing generation task.

Aggregates overnight insights for the Today page:
- Recent captures (24h)
- Link suggestions from batch_link (not auto-created, user accepts)
- Due spaced repetition reviews
- Knowledge gaps (stub cards)
"""
from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

from celery import shared_task
from sqlmodel import select

from alfred.core.database import SessionLocal
from alfred.models.doc_storage import DocumentRow
from alfred.models.zettel import ZettelCard, ZettelLink, ZettelReview

logger = logging.getLogger(__name__)


@shared_task(name="alfred.tasks.daily_briefing.generate")
def generate_daily_briefing() -> dict:
    """Aggregate overnight insights for the Today page."""
    session = SessionLocal()
    try:
        now = datetime.now(UTC)
        yesterday = now - timedelta(hours=24)

        # 1. Recent captures (24h)
        recent_docs = list(session.exec(
            select(DocumentRow)
            .where(DocumentRow.created_at >= yesterday)
            .order_by(DocumentRow.created_at.desc())
            .limit(20)
        ))
        captures = [
            {
                "id": str(doc.id),
                "title": doc.title or "Untitled",
                "source_url": doc.source_url,
                "pipeline_status": doc.pipeline_status,
                "content_type": doc.content_type,
                "created_at": doc.created_at.isoformat() if doc.created_at else None,
            }
            for doc in recent_docs
        ]

        # 2. Due reviews
        due_reviews_rows = list(session.exec(
            select(ZettelReview)
            .where(ZettelReview.due_at <= now)
            .where(ZettelReview.completed_at.is_(None))  # type: ignore[union-attr]
            .limit(20)
        ))
        due_card_ids = [r.card_id for r in due_reviews_rows]
        due_cards = {}
        if due_card_ids:
            cards = list(session.exec(
                select(ZettelCard).where(ZettelCard.id.in_(due_card_ids))
            ))
            due_cards = {c.id: c for c in cards}

        reviews = [
            {
                "review_id": r.id,
                "card_id": r.card_id,
                "card_title": due_cards.get(r.card_id, ZettelCard(title="Unknown")).title,
                "stage": r.stage,
                "due_at": r.due_at.isoformat() if r.due_at else None,
            }
            for r in due_reviews_rows
        ]

        # 3. Knowledge gaps (stub cards)
        stub_cards = list(session.exec(
            select(ZettelCard)
            .where(ZettelCard.status == "stub")
            .limit(10)
        ))
        gaps = [
            {
                "card_id": c.id,
                "title": c.title,
                "created_at": c.created_at.isoformat() if c.created_at else None,
            }
            for c in stub_cards
        ]

        # 4. Recent connections (links created in last 24h)
        recent_links = list(session.exec(
            select(ZettelLink)
            .where(ZettelLink.created_at >= yesterday)
            .limit(20)
        ))
        link_card_ids = set()
        for link in recent_links:
            link_card_ids.add(link.from_card_id)
            link_card_ids.add(link.to_card_id)
        link_cards = {}
        if link_card_ids:
            cards = list(session.exec(
                select(ZettelCard).where(ZettelCard.id.in_(list(link_card_ids)))
            ))
            link_cards = {c.id: c for c in cards}

        connections = [
            {
                "link_id": link.id,
                "from_card_id": link.from_card_id,
                "from_title": link_cards.get(link.from_card_id, ZettelCard(title="Unknown")).title,
                "to_card_id": link.to_card_id,
                "to_title": link_cards.get(link.to_card_id, ZettelCard(title="Unknown")).title,
                "type": link.type,
                "created_at": link.created_at.isoformat() if link.created_at else None,
            }
            for link in recent_links
        ]

        # 5. Overall stats
        total_cards = len(list(session.exec(
            select(ZettelCard.id).where(ZettelCard.status != "archived")
        )))
        total_links = len(list(session.exec(select(ZettelLink.id))))

        briefing = {
            "date": now.date().isoformat(),
            "generated_at": now.isoformat(),
            "captures": captures,
            "connections": connections,
            "reviews": reviews,
            "gaps": gaps,
            "stats": {
                "total_captures_24h": len(captures),
                "total_connections_24h": len(connections),
                "total_due_reviews": len(reviews),
                "total_gaps": len(gaps),
                "total_cards": total_cards,
                "total_links": total_links,
            },
        }

        logger.info(
            "Daily briefing: %d captures, %d connections, %d reviews, %d gaps",
            len(captures), len(connections), len(reviews), len(gaps),
        )
        return briefing

    finally:
        session.close()
