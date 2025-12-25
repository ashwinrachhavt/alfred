"""Zettelkasten-inspired knowledge service.

Provides CRUD for atomic cards, lightweight linking, and spaced-repetition
review scheduling. Designed to stay composable with the existing learning and
document storage services without hard coupling.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlmodel import Session, select

from alfred.core.utils import STAGE_TO_DELTA, clamp_int
from alfred.core.utils import utcnow_naive as _utcnow
from alfred.models.zettel import ZettelCard, ZettelLink, ZettelReview
from alfred.services.spaced_repetition import compute_next_review_schedule


@dataclass
class ZettelkastenService:
    """Domain service for Zettelkasten cards and reviews."""

    session: Session

    # ---------------
    # Cards
    # ---------------
    def create_card(
        self,
        *,
        title: str,
        content: str | None = None,
        summary: str | None = None,
        tags: list[str] | None = None,
        topic: str | None = None,
        source_url: str | None = None,
        document_id: str | None = None,
        importance: int = 0,
        confidence: float = 0.0,
        status: str = "active",
    ) -> ZettelCard:
        card = ZettelCard(
            title=title.strip(),
            content=content.strip() if content else None,
            summary=summary.strip() if summary else None,
            tags=tags or [],
            topic=topic.strip() if topic else None,
            source_url=source_url.strip() if source_url else None,
            document_id=document_id.strip() if document_id else None,
            importance=clamp_int(int(importance), lo=0, hi=10),
            confidence=max(0.0, min(1.0, float(confidence))),
            status=status,
        )
        self.session.add(card)
        self.session.commit()
        self.session.refresh(card)
        self._ensure_open_review(card_id=card.id or 0)
        return card

    def list_cards(
        self,
        *,
        q: str | None = None,
        topic: str | None = None,
        tag: str | None = None,
        limit: int = 50,
        skip: int = 0,
    ) -> list[ZettelCard]:
        stmt = select(ZettelCard).order_by(ZettelCard.updated_at.desc())
        if q:
            like = f"%{q.strip()}%"
            stmt = stmt.where(
                ZettelCard.title.ilike(like)
                | ZettelCard.content.ilike(like)
                | ZettelCard.summary.ilike(like)
            )
        if topic:
            stmt = stmt.where(ZettelCard.topic == topic.strip())
        stmt = stmt.offset(clamp_int(skip, lo=0, hi=10_000)).limit(clamp_int(limit, lo=1, hi=200))
        results = list(self.session.exec(stmt))
        if tag:
            results = [c for c in results if tag in (c.tags or [])]
        return results

    def get_card(self, card_id: int) -> ZettelCard | None:
        return self.session.get(ZettelCard, card_id)

    def update_card(self, card: ZettelCard, **fields) -> ZettelCard:
        if "title" in fields and fields["title"]:
            card.title = str(fields["title"]).strip()
        if "content" in fields:
            card.content = fields["content"]
        if "summary" in fields:
            card.summary = fields["summary"]
        if "tags" in fields:
            card.tags = fields["tags"] or []
        if "topic" in fields:
            card.topic = fields["topic"]
        if "source_url" in fields:
            card.source_url = fields["source_url"]
        if "document_id" in fields:
            card.document_id = fields["document_id"]
        if "status" in fields and fields["status"]:
            card.status = str(fields["status"])
        if "importance" in fields and fields["importance"] is not None:
            card.importance = clamp_int(int(fields["importance"]), lo=0, hi=10)
        if "confidence" in fields and fields["confidence"] is not None:
            card.confidence = max(0.0, min(1.0, float(fields["confidence"])))
        card.updated_at = _utcnow()
        self.session.add(card)
        self.session.commit()
        self.session.refresh(card)
        return card

    # ---------------
    # Links
    # ---------------
    def create_link(
        self,
        *,
        from_card_id: int,
        to_card_id: int,
        type: str = "reference",
        context: str | None = None,
        bidirectional: bool = True,
    ) -> list[ZettelLink]:
        links: list[ZettelLink] = []
        existing = self.session.exec(
            select(ZettelLink).where(
                (ZettelLink.from_card_id == from_card_id)
                & (ZettelLink.to_card_id == to_card_id)
                & (ZettelLink.type == type)
            )
        ).first()
        if not existing:
            links.append(
                ZettelLink(
                    from_card_id=from_card_id,
                    to_card_id=to_card_id,
                    type=type,
                    context=context,
                    bidirectional=bidirectional,
                )
            )

        if bidirectional:
            reverse_exists = self.session.exec(
                select(ZettelLink).where(
                    (ZettelLink.from_card_id == to_card_id)
                    & (ZettelLink.to_card_id == from_card_id)
                    & (ZettelLink.type == type)
                )
            ).first()
            if not reverse_exists:
                links.append(
                    ZettelLink(
                        from_card_id=to_card_id,
                        to_card_id=from_card_id,
                        type=type,
                        context=context,
                        bidirectional=bidirectional,
                    )
                )
        for link in links:
            self.session.add(link)
        self.session.commit()
        for link in links:
            self.session.refresh(link)
        return links

    def list_links(self, *, card_id: int) -> list[ZettelLink]:
        stmt = select(ZettelLink).where(
            (ZettelLink.from_card_id == card_id) | (ZettelLink.to_card_id == card_id)
        )
        return list(self.session.exec(stmt))

    # ---------------
    # Reviews (spaced repetition)
    # ---------------
    def list_due_reviews(
        self, *, now: datetime | None = None, limit: int = 50
    ) -> list[ZettelReview]:
        now = now or _utcnow()
        stmt = (
            select(ZettelReview)
            .where(ZettelReview.completed_at.is_(None))
            .where(ZettelReview.due_at <= now)
            .order_by(ZettelReview.due_at.asc())
            .limit(int(limit))
        )
        return list(self.session.exec(stmt))

    def _ensure_open_review(self, *, card_id: int) -> ZettelReview:
        stmt = (
            select(ZettelReview)
            .where(ZettelReview.card_id == card_id)
            .where(ZettelReview.completed_at.is_(None))
            .order_by(ZettelReview.due_at.asc())
        )
        existing = self.session.exec(stmt).first()
        if existing:
            return existing

        due_at = _utcnow() + STAGE_TO_DELTA[1]
        review = ZettelReview(card_id=card_id, stage=1, iteration=1, due_at=due_at)
        self.session.add(review)
        self.session.commit()
        self.session.refresh(review)
        return review

    def complete_review(
        self,
        *,
        review: ZettelReview,
        score: float | None,
        pass_threshold: float = 0.8,
    ) -> ZettelReview:
        now = _utcnow()
        review.completed_at = now
        review.score = score
        review.updated_at = now
        self.session.add(review)

        next_ = compute_next_review_schedule(
            now=now,
            stage=int(review.stage),
            iteration=int(review.iteration),
            score=score,
            pass_threshold=pass_threshold,
            stage_to_delta=STAGE_TO_DELTA,
            max_stage=3,
            reset_stage=1,
        )

        self.session.add(
            ZettelReview(
                card_id=review.card_id,
                stage=next_.stage,
                iteration=next_.iteration,
                due_at=next_.due_at,
            )
        )
        self.session.commit()
        self.session.refresh(review)
        return review

    # ---------------
    # Graph summary
    # ---------------
    def graph_summary(self) -> dict:
        nodes = []
        edges: list[dict] = []

        cards: list[ZettelCard] = list(self.session.exec(select(ZettelCard)))
        links: list[ZettelLink] = list(self.session.exec(select(ZettelLink)))

        degree: dict[int, int] = {}
        for link in links:
            degree[link.from_card_id] = degree.get(link.from_card_id, 0) + 1
            degree[link.to_card_id] = degree.get(link.to_card_id, 0) + 1

        for card in cards:
            nodes.append(
                {
                    "id": card.id,
                    "title": card.title,
                    "topic": card.topic,
                    "tags": card.tags or [],
                    "degree": degree.get(card.id or 0, 0),
                }
            )
        for link in links:
            edges.append(
                {
                    "from": link.from_card_id,
                    "to": link.to_card_id,
                    "type": link.type,
                }
            )
        return {"nodes": nodes, "edges": edges}
