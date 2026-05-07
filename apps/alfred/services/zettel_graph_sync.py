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

    def _project_card(self, card: ZettelCard) -> None:
        """Project one active card to Neo4j. Caller must filter archived/None-id cards."""
        self.graph.upsert_zettel(
            card_id=card.id,  # caller guarantees not None
            title=card.title,
            topic=card.topic,
            tags=list(card.tags or []),
            bloom_level=card.bloom_level,
            cluster_id=None,
        )

    def upsert_card(self, card_id: int) -> None:
        """Project a single card. Archived or missing cards get deleted from Neo4j."""
        card = self.session.get(ZettelCard, card_id)
        if card is None or card.status == "archived":
            self.graph.delete_zettel(card_id=card_id)
            return
        if card.id is None:
            logger.warning("Skipping projection for card with no id (title=%r)", card.title)
            return
        self._project_card(card)

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
        """Wipe and repopulate the Zettel subgraph.

        Not transactional: there is a brief window between the wipe and the
        first card upsert where reads return an empty graph. Callers should
        schedule this as a background task and treat reads as eventually
        consistent. A future upgrade may switch to upsert-then-prune to close
        this window.
        """
        self.graph.wipe_zettel_subgraph()

        cards = list(
            self.session.exec(select(ZettelCard).where(ZettelCard.status == "active"))
        )
        projected_ids: set[int] = set()
        for card in cards:
            if card.id is None:
                logger.warning("Skipping rebuild for card with no id (title=%r)", card.title)
                continue
            self._project_card(card)
            projected_ids.add(card.id)

        links = list(self.session.exec(select(ZettelLink)))
        edge_count = 0
        for link in links:
            if link.from_card_id in projected_ids and link.to_card_id in projected_ids:
                self.graph.link_zettels(
                    from_id=link.from_card_id,
                    to_id=link.to_card_id,
                    type_=link.type,
                    bidirectional=bool(link.bidirectional),
                )
                edge_count += 1

        logger.info(
            "Zettel graph rebuild: %d nodes, %d edges", len(projected_ids), edge_count
        )
        return {"nodes_synced": len(projected_ids), "edges_synced": edge_count}
