"""Zettelkasten-inspired knowledge service.

Provides CRUD for atomic cards, lightweight linking, and spaced-repetition
review scheduling. Designed to stay composable with the existing learning and
document storage services without hard coupling.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from math import sqrt

from sqlalchemy import func
from sqlalchemy import text as sa_text
from sqlmodel import Session, select

from alfred.core.dependencies import get_qdrant_client
from alfred.core.utils import STAGE_TO_DELTA, clamp_int
from alfred.core.utils import utcnow_naive as _utcnow
from alfred.models.zettel import ZettelCard, ZettelLink, ZettelReview
from alfred.schemas.zettel import LinkQuality, LinkSuggestion
from alfred.services.spaced_repetition import compute_next_review_schedule
from alfred.services.zettel_graph_summary import ZettelGraphSummaryService
from alfred.services.zettel_links import (
    UNSET as _UNSET,
)
from alfred.services.zettel_links import (
    LinkContextPatch,
    ZettelLinkService,
)
from alfred.services.zettel_wiki_links import ZettelWikiLinkService

log = logging.getLogger(__name__)


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
        session_id: int | None = None,
        bloom_level: int = 1,
        bloom_source: str = "backfill",
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
            session_id=session_id,
            bloom_level=clamp_int(int(bloom_level), lo=1, hi=6),
            bloom_source=(bloom_source or "backfill").strip() or "backfill",
        )
        self.session.add(card)
        self.session.commit()
        self.session.refresh(card)
        self._ensure_open_review(card_id=card.id or 0)
        # Close the crud-vector-sync-gap: push the new card into Qdrant so
        # semantic search / similarity features see it immediately. Sync
        # failures must NOT fail card creation — the card is already saved
        # in Postgres; the embedding can be backfilled later.
        try:
            self.ensure_embedding(card)
        except Exception as exc:
            log.warning(
                "ensure_embedding failed for card %s: %s",
                card.id,
                exc,
                exc_info=True,
            )
        return card

    def create_stub_card(self, title: str) -> ZettelCard:
        """Create a stub card for an unresolved wiki-link target."""
        card = ZettelCard(title=title, content="", status="stub", tags=[], importance=0)
        self.session.add(card)
        self.session.commit()
        self.session.refresh(card)
        return card

    def create_cards_batch(self, cards_data: list[dict]) -> list[ZettelCard]:
        """Create multiple zettel cards in a single transaction.

        Per-card dict keys supported:
            title (required), content, summary, tags, topic, source_url,
            document_id, importance, confidence, status, session_id,
            bloom_level, bloom_source
        """
        cards = []
        for data in cards_data:
            bloom_level = clamp_int(int(data.get("bloom_level", 1)), lo=1, hi=6)
            bloom_source_raw = data.get("bloom_source") or "backfill"
            bloom_source = str(bloom_source_raw).strip() or "backfill"
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
                session_id=data.get("session_id"),
                bloom_level=bloom_level,
                bloom_source=bloom_source,
            )
            cards.append(card)
        self.session.add_all(cards)
        self.session.commit()
        for card in cards:
            self.session.refresh(card)
            self._ensure_open_review(card_id=card.id or 0)
            # Close the crud-vector-sync-gap per-card. Isolating the try
            # inside the loop means one embedding failure can't block
            # Qdrant sync for the remaining cards in the batch.
            try:
                self.ensure_embedding(card)
            except Exception as exc:
                log.warning(
                    "ensure_embedding failed for card %s: %s",
                    card.id,
                    exc,
                    exc_info=True,
                )
        return cards

    def _apply_card_filters(
        self,
        stmt,
        *,
        q=None,
        topic=None,
        tags=None,
        document_id=None,
        status="active",
        importance_min=None,
    ):
        """Apply common card filters to a SELECT statement."""
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
        else:
            stmt = stmt.where(ZettelCard.status != "archived")
        if importance_min is not None:
            stmt = stmt.where(ZettelCard.importance >= importance_min)
        if tags:
            # Single containment check instead of per-tag loop
            stmt = stmt.where(
                sa_text("tags::jsonb @> :all_tags::jsonb").bindparams(all_tags=json.dumps(tags))
            )
        return stmt

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
        stmt = self._apply_card_filters(
            stmt,
            q=q,
            topic=topic,
            tags=tags,
            document_id=document_id,
            status=status,
            importance_min=importance_min,
        )

        sort_col = _ALLOWED_SORT_COLUMNS.get(sort_by or "", ZettelCard.updated_at)
        if sort_dir == "asc":
            stmt = stmt.order_by(sort_col.asc())  # type: ignore[union-attr]
        else:
            stmt = stmt.order_by(sort_col.desc())  # type: ignore[union-attr]

        stmt = stmt.offset(clamp_int(skip, lo=0, hi=10_000)).limit(clamp_int(limit, lo=1, hi=200))
        return list(self.session.exec(stmt))

    def count_cards(
        self,
        *,
        q: str | None = None,
        topic: str | None = None,
        tags: list[str] | None = None,
        document_id: str | None = None,
        status: str | None = None,
        importance_min: int | None = None,
    ) -> int:
        """Count cards matching filters (for pagination)."""
        stmt = select(func.count()).select_from(ZettelCard)
        stmt = self._apply_card_filters(
            stmt,
            q=q,
            topic=topic,
            tags=tags,
            document_id=document_id,
            status=status,
            importance_min=importance_min,
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
        return ZettelLinkService(self.session).create_link(
            from_card_id=from_card_id,
            to_card_id=to_card_id,
            type=type,
            context=context,
            bidirectional=bidirectional,
        )

    def list_links(self, *, card_id: int) -> list[ZettelLink]:
        return ZettelLinkService(self.session).list_links(card_id=card_id)

    def delete_link(self, link_id: int) -> bool:
        """Delete a link by ID. Returns True if deleted, False if not found."""
        return ZettelLinkService(self.session).delete_link(link_id)

    def update_link(
        self,
        link_id: int,
        *,
        type: str | None = None,
        context: LinkContextPatch = _UNSET,
        bidirectional: bool | None = None,
    ) -> ZettelLink | None:
        """Patch a link and synchronize the reverse row.

        Context semantics (important — differs from type/bidirectional):
        - context omitted (sentinel _UNSET): no change.
        - context=None: clear the context to NULL on forward and reverse rows.
        - context=str: set the context to that string.

        Reverse-row sync rules:
        - type change: reverse row (if exists) gets the same new type. Any
          row at (from, to, new_type) or (to, from, new_type) that would
          collide with the unique index `ix_zettel_links_unique` is deleted
          first.
        - bidirectional False -> True: create a reverse row.
        - bidirectional True  -> False: delete the reverse row if it exists.

        Returns the updated forward link, or None if not found. Raises
        ValueError if `type` normalizes to the empty string.
        """
        return ZettelLinkService(self.session).update_link(
            link_id,
            type=type,
            context=context,
            bidirectional=bidirectional,
        )

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
        return ZettelGraphSummaryService(self.session).graph_summary()

    def extended_graph_summary(
        self,
        include_clusters: bool = False,
        include_gaps: bool = False,
    ) -> dict:
        """Extended graph summary with clusters, gaps, review due dates, and metadata."""
        return ZettelGraphSummaryService(self.session).extended_graph_summary(
            include_clusters=include_clusters,
            include_gaps=include_gaps,
        )

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

    def semantic_search_cards(
        self,
        query: str,
        *,
        topic: str | None = None,
        limit: int = 10,
    ) -> list[tuple[ZettelCard, float]]:
        """Return scored card matches for agent KB search.

        This uses the local text search path as a deterministic fallback. The
        score is intentionally coarse because callers only need ordering and a
        common result shape for merging with document search hits.
        """

        cards = self.list_cards(q=query, topic=topic, limit=limit)
        return [(card, 1.0) for card in cards]

    def list_backlinks(self, card_id: int) -> list[dict]:
        """Return all wiki-links pointing TO the given card.

        Queries the wiki_links table and joins to source titles.
        Also includes incoming ZettelLinks (from the graph link system).
        """
        return ZettelWikiLinkService(self.session).list_backlinks(card_id)

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
        ZettelWikiLinkService(self.session).sync_wiki_links(
            source_type=source_type,
            source_id=source_id,
            target_card_ids=target_card_ids,
        )

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
        self, card_id: int, *, threshold: float = 0.5, limit: int = 10
    ) -> list[tuple[ZettelCard, LinkQuality]]:
        card = self.session.get(ZettelCard, card_id)
        if not card:
            raise ValueError("Card not found")

        card = self.ensure_embedding(card)
        base_embedding = card.embedding or []
        if not base_embedding:
            return []

        existing_links = self._existing_links(card_id)

        qdrant = get_qdrant_client()
        if qdrant is not None:
            return self._find_similar_via_qdrant(
                card,
                base_embedding,
                existing_links,
                qdrant,
                threshold=threshold,
                limit=limit,
            )
        return self._find_similar_via_scan(
            card,
            card_id,
            base_embedding,
            existing_links,
            threshold=threshold,
            limit=limit,
        )

    def _find_similar_via_qdrant(
        self,
        card: ZettelCard,
        base_embedding: list[float],
        existing_links: set,
        qdrant,
        *,
        threshold: float,
        limit: int,
    ) -> list[tuple[ZettelCard, LinkQuality]]:
        from alfred.core.settings import settings

        try:
            results = qdrant.query_points(
                collection_name=settings.qdrant_zettels_collection,
                query=base_embedding,
                limit=limit * 3,
                score_threshold=threshold,
            )
        except Exception:
            return self._find_similar_via_scan(
                card,
                card.id,
                base_embedding,
                existing_links,
                threshold=threshold,
                limit=limit,
            )

        scores_by_id: dict[int, float] = {}
        for hit in results.points:
            hit_id = int(hit.id) if not isinstance(hit.id, int) else hit.id
            if hit_id == card.id or (card.id, hit_id) in existing_links:
                continue
            scores_by_id[hit_id] = hit.score

        if not scores_by_id:
            return []

        candidate_stmt = select(ZettelCard).where(
            ZettelCard.id.in_(list(scores_by_id.keys()))
        )
        candidates = self.session.exec(candidate_stmt).all()

        scored: list[tuple[ZettelCard, LinkQuality]] = [
            (cand, self._quality(card, cand, semantic_score=scores_by_id[cand.id]))
            for cand in candidates
            if cand.id in scores_by_id
        ]

        scored.sort(key=lambda item: item[1].composite_score, reverse=True)
        return scored[:limit]

    def _find_similar_via_scan(
        self,
        card: ZettelCard,
        card_id: int,
        base_embedding: list[float],
        existing_links: set,
        *,
        threshold: float,
        limit: int,
    ) -> list[tuple[ZettelCard, LinkQuality]]:
        """Original O(n) fallback when Qdrant is unavailable."""
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
    def _build_ai_card_messages(
        self,
        *,
        prompt: str | None = None,
        content: str | None = None,
        topic: str | None = None,
        tags: list[str] | None = None,
    ) -> list[dict[str, str]]:
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

        return [
            {"role": "system", "content": system_msg},
            {"role": "user", "content": user_msg},
        ]

    def _parse_ai_card_payload(
        self,
        raw: str,
        *,
        topic: str | None = None,
        tags: list[str] | None = None,
    ) -> dict:
        import json

        text = raw.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1] if "\n" in text else text[3:]
            if text.endswith("```"):
                text = text[:-3]
            text = text.strip()

        data = json.loads(text)

        return {
            "title": data.get("title", "Untitled"),
            "content": data.get("content"),
            "summary": data.get("summary"),
            "tags": data.get("tags") or tags or [],
            "topic": data.get("topic") or topic,
            "importance": data.get("importance", 5),
            "confidence": data.get("confidence", 0.7),
            "status": "active",
        }

    def generate_card_from_ai(
        self,
        *,
        prompt: str | None = None,
        content: str | None = None,
        topic: str | None = None,
        tags: list[str] | None = None,
    ) -> ZettelCard:
        """Use an LLM to generate a structured zettel card from a prompt or content."""
        data = self.generate_card_payload_from_ai(
            prompt=prompt,
            content=content,
            topic=topic,
            tags=tags,
        )

        return self.create_card(**data)

    def generate_card_payload_from_ai(
        self,
        *,
        prompt: str | None = None,
        content: str | None = None,
        topic: str | None = None,
        tags: list[str] | None = None,
    ) -> dict:
        """Use an LLM to generate a structured zettel payload without persisting it."""
        from alfred.core.llm_factory import get_chat_model

        llm = get_chat_model()
        response = llm.invoke(
            self._build_ai_card_messages(
                prompt=prompt,
                content=content,
                topic=topic,
                tags=tags,
            )
        )

        raw = response.content if hasattr(response, "content") else str(response)
        return self._parse_ai_card_payload(str(raw), topic=topic, tags=tags)

    def stream_card_payload_text_from_ai(
        self,
        *,
        prompt: str | None = None,
        content: str | None = None,
        topic: str | None = None,
        tags: list[str] | None = None,
    ):
        """Yield raw generation tokens, then the parsed zettel payload."""
        from alfred.core.llm_factory import get_chat_model

        llm = get_chat_model()
        chunks: list[str] = []
        for part in llm.stream(
            self._build_ai_card_messages(
                prompt=prompt,
                content=content,
                topic=topic,
                tags=tags,
            )
        ):
            raw_content = getattr(part, "content", "")
            if isinstance(raw_content, str):
                text = raw_content
            elif isinstance(raw_content, list):
                text = "".join(str(item) for item in raw_content)
            else:
                text = str(raw_content)
            if text:
                chunks.append(text)
                yield {"type": "token", "content": text}

        raw = "".join(chunks)
        yield {
            "type": "done",
            "draft": self._parse_ai_card_payload(raw, topic=topic, tags=tags),
            "raw": raw,
        }
