"""Zettelkasten-inspired knowledge service.

Provides CRUD for atomic cards, lightweight linking, and spaced-repetition
review scheduling. Designed to stay composable with the existing learning and
document storage services without hard coupling.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from math import sqrt

from sqlalchemy import func, text as sa_text
from sqlmodel import Session, select

from alfred.core.utils import STAGE_TO_DELTA, clamp_int
from alfred.core.utils import utcnow_naive as _utcnow
from alfred.models.zettel import ZettelCard, ZettelLink, ZettelReview
from alfred.schemas.zettel import LinkQuality, LinkSuggestion
from alfred.services.spaced_repetition import compute_next_review_schedule


def _cosine_similarity(a: Iterable[float], b: Iterable[float]) -> float:
    a_list = list(a)
    b_list = list(b)
    if not a_list or not b_list or len(a_list) != len(b_list):
        return 0.0
    dot = sum(x * y for x, y in zip(a_list, b_list, strict=False))
    norm_a = sqrt(sum(x * x for x in a_list))
    norm_b = sqrt(sum(y * y for y in b_list))
    denom = norm_a * norm_b
    if denom == 0:
        return 0.0
    return dot / denom


def _temporal_proximity_days(a: datetime | None, b: datetime | None) -> float | None:
    if not a or not b:
        return None
    return abs((a - b).days)


LINK_QUALITY_HIGH_CONFIDENCE_THRESHOLD = 0.8
LINK_QUALITY_MEDIUM_CONFIDENCE_THRESHOLD = 0.6

_ALLOWED_SORT_COLUMNS = {
    "title": ZettelCard.title,
    "created_at": ZettelCard.created_at,
    "updated_at": ZettelCard.updated_at,
    "importance": ZettelCard.importance,
    "confidence": ZettelCard.confidence,
}


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

    def create_cards_batch(self, cards_data: list[dict]) -> list[ZettelCard]:
        """Create multiple zettel cards in a single transaction."""
        cards = []
        for data in cards_data:
            card = ZettelCard(
                title=str(data["title"]).strip(),
                content=data.get("content"),
                summary=data.get("summary"),
                tags=data.get("tags") or [],
                topic=data.get("topic"),
                source_url=data.get("source_url"),
                document_id=data.get("document_id"),
                importance=clamp_int(int(data.get("importance", 0)), lo=0, hi=10),
                confidence=max(0.0, min(1.0, float(data.get("confidence", 0.0)))),
                status=data.get("status", "active"),
            )
            cards.append(card)
        self.session.add_all(cards)
        self.session.commit()
        for card in cards:
            self.session.refresh(card)
            self._ensure_open_review(card_id=card.id or 0)
        return cards

    def list_cards(
        self,
        *,
        q: str | None = None,
        topic: str | None = None,
        tags: list[str] | None = None,
        document_id: str | None = None,
        sort_by: str | None = None,
        sort_dir: str | None = None,
        importance_min: int | None = None,
        status: str | None = "active",
        limit: int = 50,
        skip: int = 0,
    ) -> list[ZettelCard]:
        stmt = select(ZettelCard)

        sort_col = _ALLOWED_SORT_COLUMNS.get(sort_by or "", ZettelCard.updated_at)
        if sort_dir == "asc":
            stmt = stmt.order_by(sort_col.asc())  # type: ignore[union-attr]
        else:
            stmt = stmt.order_by(sort_col.desc())  # type: ignore[union-attr]

        if q:
            like = f"%{q.strip()}%"
            stmt = stmt.where(
                ZettelCard.title.ilike(like)
                | ZettelCard.content.ilike(like)
                | ZettelCard.summary.ilike(like)
            )
        if topic:
            stmt = stmt.where(ZettelCard.topic == topic.strip())
        if document_id:
            stmt = stmt.where(ZettelCard.document_id == document_id.strip())
        if status:
            stmt = stmt.where(ZettelCard.status == status)
        if importance_min is not None:
            stmt = stmt.where(ZettelCard.importance >= importance_min)

        if tags:
            for i, t in enumerate(tags):
                param = f"tag_val_{i}"
                stmt = stmt.where(
                    sa_text(f"tags::jsonb @> :{param}::jsonb").bindparams(
                        **{param: json.dumps([t])}
                    )
                )

        stmt = stmt.offset(clamp_int(skip, lo=0, hi=10_000)).limit(clamp_int(limit, lo=1, hi=200))
        return list(self.session.exec(stmt))

    def count_cards(
        self,
        *,
        q: str | None = None,
        topic: str | None = None,
        tags: list[str] | None = None,
        document_id: str | None = None,
        importance_min: int | None = None,
        status: str | None = "active",
    ) -> int:
        """Return total count of cards matching the given filters (no pagination)."""
        stmt = select(func.count()).select_from(ZettelCard)

        if q:
            like = f"%{q.strip()}%"
            stmt = stmt.where(
                ZettelCard.title.ilike(like)
                | ZettelCard.content.ilike(like)
                | ZettelCard.summary.ilike(like)
            )
        if topic:
            stmt = stmt.where(ZettelCard.topic == topic.strip())
        if document_id:
            stmt = stmt.where(ZettelCard.document_id == document_id.strip())
        if status:
            stmt = stmt.where(ZettelCard.status == status)
        if importance_min is not None:
            stmt = stmt.where(ZettelCard.importance >= importance_min)

        if tags:
            for i, t in enumerate(tags):
                param = f"tag_val_{i}"
                stmt = stmt.where(
                    sa_text(f"tags::jsonb @> :{param}::jsonb").bindparams(
                        **{param: json.dumps([t])}
                    )
                )

        result = self.session.exec(stmt).one()
        return int(result)

    def get_card(self, card_id: int) -> ZettelCard | None:
        return self.session.get(ZettelCard, card_id)

    def update_card(self, card: ZettelCard, **fields) -> ZettelCard:
        text_changed = False
        if fields.get("title"):
            card.title = str(fields["title"]).strip()
            text_changed = True
        if "content" in fields:
            card.content = fields["content"]
            text_changed = True
        if "summary" in fields:
            card.summary = fields["summary"]
            text_changed = True
        if "tags" in fields:
            card.tags = fields["tags"] or []
        if "topic" in fields:
            card.topic = fields["topic"]
        if "source_url" in fields:
            card.source_url = fields["source_url"]
        if "document_id" in fields:
            card.document_id = fields["document_id"]
        if fields.get("status"):
            card.status = str(fields["status"])
        if "importance" in fields and fields["importance"] is not None:
            card.importance = clamp_int(int(fields["importance"]), lo=0, hi=10)
        if "confidence" in fields and fields["confidence"] is not None:
            card.confidence = max(0.0, min(1.0, float(fields["confidence"])))
        if text_changed:
            # Avoid serving stale similarity results; embedding will be re-generated on demand.
            card.embedding = None
        card.updated_at = _utcnow()
        self.session.add(card)
        self.session.commit()
        self.session.refresh(card)
        return card

    def archive_card(self, card: ZettelCard, *, remove_links: bool = True) -> ZettelCard:
        """Soft-delete a card by setting status to 'archived' and optionally removing its links."""
        card.status = "archived"
        card.updated_at = _utcnow()
        self.session.add(card)
        if remove_links:
            links = self.list_links(card_id=card.id or 0)
            for link in links:
                self.session.delete(link)
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

    def delete_link(self, link_id: int) -> bool:
        """Delete a link by ID. Returns True if deleted, False if not found."""
        link = self.session.get(ZettelLink, link_id)
        if not link:
            return False
        # Also delete the reverse link if it exists (bidirectional)
        if link.bidirectional:
            reverse = self.session.exec(
                select(ZettelLink).where(
                    (ZettelLink.from_card_id == link.to_card_id)
                    & (ZettelLink.to_card_id == link.from_card_id)
                    & (ZettelLink.type == link.type)
                )
            ).first()
            if reverse:
                self.session.delete(reverse)
        self.session.delete(link)
        self.session.commit()
        return True

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

    # ---------------
    # Wiki-link search & backlinks
    # ---------------
    def search_cards_unified(
        self,
        query: str | None = None,
        *,
        context_card_id: int | None = None,
        text_limit: int = 10,
        ai_limit: int = 5,
    ) -> dict:
        """Combined text + AI search for wiki-link autocomplete.

        Text matches (ILIKE) return instantly. AI suggestions are optional
        and only computed when context_card_id is provided.
        """
        # Text search — fast, SQL-only
        text_matches: list[dict] = []
        stmt = select(ZettelCard).where(ZettelCard.status != "archived")
        if query and query.strip():
            stmt = stmt.where(ZettelCard.title.ilike(f"%{query.strip()}%"))  # type: ignore[union-attr]
        stmt = stmt.order_by(ZettelCard.updated_at.desc()).limit(text_limit)
        for card in self.session.exec(stmt):
            text_matches.append(
                {
                    "id": card.id,
                    "title": card.title,
                    "topic": card.topic,
                    "tags": card.tags or [],
                    "status": card.status,
                }
            )

        # AI suggestions — optional, uses suggest_links engine
        ai_suggestions: list[dict] = []
        if context_card_id is not None:
            try:
                suggestions = self.suggest_links(
                    card_id=context_card_id,
                    min_confidence=0.5,
                    limit=ai_limit,
                )
                for s in suggestions:
                    ai_suggestions.append(
                        {
                            "id": s.to_card_id,
                            "title": s.to_title,
                            "topic": s.to_topic,
                            "tags": s.to_tags or [],
                            "score": round(s.scores.composite_score, 2),
                            "reason": s.reason,
                        }
                    )
            except Exception:
                # Degraded mode: AI suggestions unavailable
                pass

        return {"text_matches": text_matches, "ai_suggestions": ai_suggestions}

    def list_backlinks(self, card_id: int) -> list[dict]:
        """Return all wiki-links pointing TO the given card.

        Queries the wiki_links table and joins to source titles.
        Also includes incoming ZettelLinks (from the graph link system).
        """
        import uuid as _uuid

        from alfred.models.notes import NoteRow
        from alfred.models.zettel import WikiLink

        backlinks: list[dict] = []

        # Wiki-links (from notes/zettels)
        wiki_rows = list(
            self.session.exec(
                select(WikiLink).where(WikiLink.target_card_id == card_id)
            )
        )

        # Batch-fetch source titles to avoid N+1
        zettel_source_ids = [
            int(wl.source_id) for wl in wiki_rows if wl.source_type == "zettel"
        ]
        note_source_ids = [
            wl.source_id for wl in wiki_rows if wl.source_type == "note"
        ]

        zettel_titles: dict[int, str] = {}
        if zettel_source_ids:
            cards = self.session.exec(
                select(ZettelCard).where(ZettelCard.id.in_(zettel_source_ids))
            )
            zettel_titles = {c.id: c.title for c in cards if c.id is not None}

        note_titles: dict[str, str] = {}
        if note_source_ids:
            note_uuids = []
            for sid in note_source_ids:
                try:
                    note_uuids.append(_uuid.UUID(sid))
                except (ValueError, TypeError):
                    pass
            if note_uuids:
                notes = self.session.exec(
                    select(NoteRow).where(NoteRow.id.in_(note_uuids))
                )
                note_titles = {str(n.id): n.title for n in notes}

        for wl in wiki_rows:
            if wl.source_type == "zettel":
                source_title = zettel_titles.get(int(wl.source_id), "Unknown")
            elif wl.source_type == "note":
                source_title = note_titles.get(wl.source_id, "Unknown")
            else:
                source_title = "Unknown"
            backlinks.append(
                {
                    "source_type": wl.source_type,
                    "source_id": wl.source_id,
                    "source_title": source_title,
                    "created_at": wl.created_at,
                }
            )

        # Also include incoming ZettelLinks (graph-created links)
        incoming = list(
            self.session.exec(
                select(ZettelLink).where(ZettelLink.to_card_id == card_id)
            )
        )
        seen_card_ids = {
            int(bl["source_id"])
            for bl in backlinks
            if bl["source_type"] == "zettel"
        }
        # Batch-fetch source cards for incoming ZettelLinks
        incoming_card_ids = [
            link.from_card_id
            for link in incoming
            if link.from_card_id not in seen_card_ids
        ]
        incoming_titles: dict[int, str] = {}
        if incoming_card_ids:
            cards = self.session.exec(
                select(ZettelCard).where(ZettelCard.id.in_(incoming_card_ids))
            )
            incoming_titles = {c.id: c.title for c in cards if c.id is not None}

        for link in incoming:
            if link.from_card_id in seen_card_ids:
                continue
            title = incoming_titles.get(link.from_card_id)
            if title:
                backlinks.append(
                    {
                        "source_type": "zettel",
                        "source_id": str(link.from_card_id),
                        "source_title": title,
                        "created_at": link.created_at,
                    }
                )

        return backlinks

    def sync_wiki_links(
        self,
        *,
        source_type: str,
        source_id: str,
        target_card_ids: list[int],
    ) -> None:
        """Sync wiki-links for a source document.

        Diffs the provided card IDs against existing wiki_links rows.
        Creates missing links, deletes removed links.
        """
        from alfred.models.zettel import WikiLink

        existing = list(
            self.session.exec(
                select(WikiLink).where(
                    (WikiLink.source_type == source_type)
                    & (WikiLink.source_id == source_id)
                )
            )
        )
        existing_targets = {wl.target_card_id: wl for wl in existing}
        desired_targets = set(target_card_ids)

        # Delete removed
        for target_id, wl in existing_targets.items():
            if target_id not in desired_targets:
                self.session.delete(wl)

        # Create new
        for target_id in desired_targets:
            if target_id not in existing_targets:
                self.session.add(
                    WikiLink(
                        source_type=source_type,
                        source_id=source_id,
                        target_card_id=target_id,
                    )
                )

        self.session.commit()

    # ---------------
    # Embeddings / link suggestions
    # ---------------
    def embed_card(self, card: ZettelCard) -> list[float]:
        text_parts = [card.title, card.summary or "", card.content or ""]
        text = " ".join([p.strip() for p in text_parts if p and p.strip()])
        if not text:
            raise ValueError("Cannot embed empty card content")
        from alfred.core.llm_factory import get_embedding_model

        model = get_embedding_model()
        return model.embed_query(text)

    def ensure_embedding(self, card: ZettelCard) -> ZettelCard:
        if card.embedding:
            return card
        embedding = self.embed_card(card)
        card.embedding = embedding
        card.updated_at = _utcnow()
        self.session.add(card)
        self.session.commit()
        self.session.refresh(card)
        return card

    def _existing_links(self, card_id: int) -> set[tuple[int, int]]:
        links = self.session.exec(
            select(ZettelLink).where(
                (ZettelLink.from_card_id == card_id) | (ZettelLink.to_card_id == card_id)
            )
        )
        pairs: set[tuple[int, int]] = set()
        for link in links:
            pairs.add((link.from_card_id, link.to_card_id))
            pairs.add((link.to_card_id, link.from_card_id))
        return pairs

    def _quality(
        self, base: ZettelCard, candidate: ZettelCard, semantic_score: float
    ) -> LinkQuality:
        base_tags = set(base.tags or [])
        cand_tags = set(candidate.tags or [])
        tag_overlap = 0.0
        if base_tags or cand_tags:
            tag_overlap = len(base_tags & cand_tags) / len(base_tags | cand_tags or {1})
        topic_match = bool(base.topic and candidate.topic and base.topic == candidate.topic)
        citation_overlap = int(
            base.document_id is not None
            and candidate.document_id is not None
            and base.document_id == candidate.document_id
        ) + int(
            base.source_url is not None
            and candidate.source_url is not None
            and base.source_url == candidate.source_url
        )
        temporal_days = _temporal_proximity_days(base.updated_at, candidate.updated_at)
        temporal_weight = 0.0
        if temporal_days is not None:
            temporal_weight = max(0.0, 1.0 - min(30.0, temporal_days) / 30.0)

        composite = (
            0.6 * semantic_score
            + 0.15 * tag_overlap
            + 0.1 * (1.0 if topic_match else 0.0)
            + 0.1 * min(1, citation_overlap)
            + 0.05 * temporal_weight
        )

        if composite >= LINK_QUALITY_HIGH_CONFIDENCE_THRESHOLD:
            confidence = "high"
        elif composite >= LINK_QUALITY_MEDIUM_CONFIDENCE_THRESHOLD:
            confidence = "medium"
        else:
            confidence = "low"

        return LinkQuality(
            semantic_score=round(semantic_score, 4),
            tag_overlap=round(tag_overlap, 4),
            topic_match=topic_match,
            citation_overlap=citation_overlap,
            temporal_proximity_days=temporal_days,
            composite_score=round(composite, 4),
            confidence=confidence,
        )

    def find_similar_cards(
        self, card_id: int, *, threshold: float = 0.7, limit: int = 10
    ) -> list[tuple[ZettelCard, LinkQuality]]:
        card = self.session.get(ZettelCard, card_id)
        if not card:
            raise ValueError("Card not found")

        card = self.ensure_embedding(card)
        base_embedding = card.embedding or []
        if not base_embedding:
            return []

        existing_links = self._existing_links(card_id)

        candidates = self.session.exec(select(ZettelCard).where(ZettelCard.id != card_id))
        scored: list[tuple[ZettelCard, LinkQuality]] = []
        for cand in candidates:
            if cand.embedding is None:
                try:
                    cand = self.ensure_embedding(cand)
                except Exception:
                    continue
            semantic = _cosine_similarity(base_embedding, cand.embedding or [])
            if semantic < threshold:
                continue
            quality = self._quality(card, cand, semantic_score=semantic)
            if (card.id, cand.id) in existing_links:
                continue
            scored.append((cand, quality))

        scored.sort(key=lambda item: item[1].composite_score, reverse=True)
        return scored[:limit]

    def suggest_links(
        self, card_id: int, *, min_confidence: float = 0.6, limit: int = 10
    ) -> list[LinkSuggestion]:
        results = self.find_similar_cards(card_id, threshold=min_confidence, limit=limit * 2)
        suggestions: list[LinkSuggestion] = []
        for cand, quality in results:
            if quality.composite_score < min_confidence:
                continue
            reason_parts: list[str] = [f"{int(quality.semantic_score * 100)}% semantic similarity"]
            if quality.tag_overlap > 0:
                reason_parts.append(f"{int(quality.tag_overlap * 100)}% tag overlap")
            if quality.topic_match:
                reason_parts.append("same topic")
            if quality.citation_overlap:
                reason_parts.append("shared source")
            reason = ", ".join(reason_parts)
            suggestions.append(
                LinkSuggestion(
                    to_card_id=cand.id or 0,
                    to_title=cand.title,
                    to_topic=cand.topic,
                    to_tags=cand.tags,
                    reason=reason,
                    scores=quality,
                )
            )
            if len(suggestions) >= limit:
                break
        return suggestions

    # ---------------
    # AI generation
    # ---------------
    def generate_card_from_ai(
        self,
        *,
        prompt: str | None = None,
        content: str | None = None,
        topic: str | None = None,
        tags: list[str] | None = None,
    ) -> ZettelCard:
        """Use an LLM to generate a structured zettel card from a prompt or content."""
        import json

        from alfred.core.llm_factory import get_chat_model

        if not prompt and not content:
            raise ValueError("Either prompt or content must be provided")

        system_msg = (
            "You are a knowledge card generator. Given a topic/prompt or raw content, "
            "create a single atomic knowledge card (zettel). Return ONLY valid JSON with these fields:\n"
            '{"title": "...", "content": "...", "summary": "...", "tags": ["..."], '
            '"topic": "...", "importance": 5, "confidence": 0.7}\n'
            "Rules:\n"
            "- title: concise concept name (max 80 chars)\n"
            "- content: detailed explanation (2-4 sentences)\n"
            "- summary: one-sentence distillation\n"
            "- tags: 2-5 relevant tags (lowercase, no spaces)\n"
            "- topic: primary domain\n"
            "- importance: 0-10 (how foundational is this concept)\n"
            "- confidence: 0.0-1.0 (how well-established is this knowledge)"
        )

        user_msg = ""
        if prompt:
            user_msg += f"Generate a knowledge card about: {prompt}\n"
        if content:
            user_msg += f"Extract the key concept from this content:\n{content}\n"
        if topic:
            user_msg += f"Primary topic/domain: {topic}\n"
        if tags:
            user_msg += f"Suggested tags: {', '.join(tags)}\n"

        llm = get_chat_model()
        response = llm.invoke([
            {"role": "system", "content": system_msg},
            {"role": "user", "content": user_msg},
        ])

        raw = response.content if hasattr(response, "content") else str(response)
        raw = raw.strip()
        # Strip markdown code fences if present
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1] if "\n" in raw else raw[3:]
            if raw.endswith("```"):
                raw = raw[:-3]
            raw = raw.strip()

        data = json.loads(raw)

        return self.create_card(
            title=data.get("title", "Untitled"),
            content=data.get("content"),
            summary=data.get("summary"),
            tags=data.get("tags") or tags or [],
            topic=data.get("topic") or topic,
            importance=data.get("importance", 5),
            confidence=data.get("confidence", 0.7),
            status="active",
        )
