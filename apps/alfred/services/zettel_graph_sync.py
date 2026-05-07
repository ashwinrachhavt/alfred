"""Project Postgres zettel cards/links into Neo4j as a read model.

Postgres is the source of truth. Neo4j holds a redundant copy used only for
multi-hop graph queries (paths, bridges, community traversal). Drift is
acceptable as long as writes are eventually propagated.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from sqlmodel import Session, select

from alfred.models.zettel import ZettelCard, ZettelLink
from alfred.services.graph_service import GraphService

logger = logging.getLogger(__name__)


@dataclass
class ZettelGraphSync:
    session: Session
    graph: GraphService

    def upsert_card(self, card_id: int) -> None:
        """Project a single card. Archived or missing cards get deleted from Neo4j."""
        card = self.session.get(ZettelCard, card_id)
        if card is None or card.status == "archived":
            self.graph.delete_zettel(card_id=card_id)
            return
        self.graph.upsert_zettel(
            card_id=card.id or 0,
            title=card.title,
            topic=card.topic,
            tags=list(card.tags or []),
            bloom_level=card.bloom_level,
            cluster_id=None,
        )

    def delete_card(self, card_id: int) -> None:
        self.graph.delete_zettel(card_id=card_id)

    def upsert_link(self, link_id: int) -> None:
        link = self.session.get(ZettelLink, link_id)
        if link is None:
            return
        self.graph.link_zettels(
            from_id=link.from_card_id,
            to_id=link.to_card_id,
            type_=link.type,
            bidirectional=bool(link.bidirectional),
        )

    def delete_link(self, *, from_id: int, to_id: int, type_: str) -> None:
        self.graph.delete_zettel_link(from_id=from_id, to_id=to_id, type_=type_)

    def full_rebuild(self) -> dict[str, Any]:
        """Wipe and repopulate the Zettel subgraph. Safe as a background task."""
        self.graph._run("MATCH (z:Zettel) DETACH DELETE z")

        cards = list(self.session.exec(select(ZettelCard).where(ZettelCard.status == "active")))
        for card in cards:
            self.graph.upsert_zettel(
                card_id=card.id or 0,
                title=card.title,
                topic=card.topic,
                tags=list(card.tags or []),
                bloom_level=card.bloom_level,
                cluster_id=None,
            )

        card_ids = {card.id for card in cards if card.id is not None}
        links = list(self.session.exec(select(ZettelLink)))
        edge_count = 0
        for link in links:
            if link.from_card_id in card_ids and link.to_card_id in card_ids:
                self.graph.link_zettels(
                    from_id=link.from_card_id,
                    to_id=link.to_card_id,
                    type_=link.type,
                    bidirectional=bool(link.bidirectional),
                )
                edge_count += 1

        logger.info("Zettel graph rebuild: %d nodes, %d edges", len(cards), edge_count)
        return {"nodes_synced": len(cards), "edges_synced": edge_count}
