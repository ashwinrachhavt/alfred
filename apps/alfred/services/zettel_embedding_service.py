from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from math import sqrt
from typing import Iterable, List, Tuple

from sqlmodel import Session, select

from alfred.core.llm_factory import get_embedding_model
from alfred.models.zettel import ZettelCard, ZettelLink
from alfred.schemas.zettel import LinkQuality, LinkSuggestion


def _cosine_similarity(a: Iterable[float], b: Iterable[float]) -> float:
    a_list = list(a)
    b_list = list(b)
    if not a_list or not b_list or len(a_list) != len(b_list):
        return 0.0
    dot = sum(x * y for x, y in zip(a_list, b_list))
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


@dataclass
class ZettelEmbeddingService:
    """Embedding-backed link suggestion helper for Zettelkasten cards."""

    session: Session

    def embed_card(self, card: ZettelCard) -> list[float]:
        text_parts = [card.title, card.summary or "", card.content or ""]
        text = " ".join([p.strip() for p in text_parts if p and p.strip()])
        if not text:
            raise ValueError("Cannot embed empty card content")
        model = get_embedding_model()
        return model.embed_query(text)

    def ensure_embedding(self, card: ZettelCard) -> ZettelCard:
        if card.embedding:
            return card
        embedding = self.embed_card(card)
        card.embedding = embedding
        card.updated_at = datetime.utcnow()
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

        if composite >= 0.8:
            confidence = "high"
        elif composite >= 0.6:
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
    ) -> List[Tuple[ZettelCard, LinkQuality]]:
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
