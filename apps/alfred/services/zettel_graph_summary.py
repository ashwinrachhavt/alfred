"""Graph summaries for zettel cards and links."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlmodel import Session, select

from alfred.models.zettel import ZettelCard, ZettelLink, ZettelReview
from alfred.services.clustering_service import ClusteringService


@dataclass
class ZettelGraphSummaryService:
    """Build graph payloads consumed by zettel and nexus views."""

    session: Session

    def graph_summary(self) -> dict[str, list[dict[str, Any]]]:
        cards: list[ZettelCard] = list(self.session.exec(select(ZettelCard)))
        links: list[ZettelLink] = list(self.session.exec(select(ZettelLink)))
        degree = self._degree_by_card(links)

        nodes = [
            {
                "id": card.id,
                "title": card.title,
                "topic": card.topic,
                "tags": card.tags or [],
                "importance": card.importance,
                "status": card.status,
                "degree": degree.get(card.id or 0, 0),
            }
            for card in cards
        ]
        edges = [
            {
                "id": link.id,
                "from": link.from_card_id,
                "to": link.to_card_id,
                "type": link.type,
                "bidirectional": link.bidirectional,
            }
            for link in links
        ]
        return {"nodes": nodes, "edges": edges}

    def extended_graph_summary(
        self,
        include_clusters: bool = False,
        include_gaps: bool = False,
    ) -> dict[str, Any]:
        """Extended graph summary with clusters, gaps, review due dates, and metadata."""
        cards: list[ZettelCard] = list(self.session.exec(select(ZettelCard)))
        links: list[ZettelLink] = list(self.session.exec(select(ZettelLink)))
        degree = self._degree_by_card(links)
        due_by_card = self._due_by_card()

        cluster_id_by_card: dict[int, int] = {}
        clusters_out: list[dict[str, Any]] = []
        if include_clusters:
            clustering_svc = ClusteringService()
            raw_clusters = clustering_svc.detect_clusters(cards)
            if raw_clusters:
                cards_by_id = {c.id: c for c in cards if c.id is not None}
                clusters_out = clustering_svc.generate_cluster_names(raw_clusters, cards_by_id)
                for cluster in clusters_out:
                    for cid in cluster["card_ids"]:
                        cluster_id_by_card[cid] = cluster["id"]

        nodes = [
            {
                "id": card.id,
                "title": card.title,
                "topic": card.topic,
                "tags": card.tags or [],
                "degree": degree.get(card.id or 0, 0),
                "status": card.status,
                "cluster_id": cluster_id_by_card.get(card.id or 0),
                "created_at": card.created_at.isoformat() if card.created_at else None,
                "updated_at": card.updated_at.isoformat() if card.updated_at else None,
                "due_at": due_by_card.get(card.id or 0),
                "importance": card.importance,
            }
            for card in cards
        ]

        edges = [
            {
                "source": link.from_card_id,
                "target": link.to_card_id,
                "type": link.type,
            }
            for link in links
        ]

        gaps_out: list[dict[str, Any]] = []
        if include_gaps:
            gaps_out = ClusteringService().detect_knowledge_gaps(cards, links)

        embedded_count = sum(1 for card in cards if getattr(card, "embedding", None))
        total_cards = len(cards)
        coverage_pct = round((embedded_count / total_cards * 100) if total_cards else 0.0, 1)

        return {
            "nodes": nodes,
            "edges": edges,
            "clusters": clusters_out,
            "gaps": gaps_out,
            "meta": {
                "total_cards": total_cards,
                "total_edges": len(edges),
                "embedding_coverage_pct": coverage_pct,
                "cluster_count": len(clusters_out),
            },
        }

    @staticmethod
    def _degree_by_card(links: list[ZettelLink]) -> dict[int, int]:
        degree: dict[int, int] = {}
        for link in links:
            degree[link.from_card_id] = degree.get(link.from_card_id, 0) + 1
            degree[link.to_card_id] = degree.get(link.to_card_id, 0) + 1
        return degree

    def _due_by_card(self) -> dict[int, str]:
        open_reviews = self.session.exec(
            select(ZettelReview).where(ZettelReview.completed_at.is_(None))  # type: ignore[union-attr]
        )
        due_by_card: dict[int, str] = {}
        for review in open_reviews:
            iso = review.due_at.isoformat() if review.due_at else None
            if iso and (review.card_id not in due_by_card or iso < due_by_card[review.card_id]):
                due_by_card[review.card_id] = iso
        return due_by_card
