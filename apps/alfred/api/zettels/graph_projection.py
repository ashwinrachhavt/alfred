"""Best-effort Neo4j projection hooks for zettel route mutations."""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from sqlmodel import Session

from alfred.core.dependencies import get_graph_service
from alfred.services.zettel_graph_sync import ZettelGraphSync

logger = logging.getLogger(__name__)

GraphServiceFactory = Callable[[], Any | None]
SyncFactory = Callable[..., Any]


def upsert_card(
    card_id: int | None,
    session: Session,
    *,
    graph_service_factory: GraphServiceFactory = get_graph_service,
    sync_factory: SyncFactory = ZettelGraphSync,
) -> bool:
    """Project a card to Neo4j. Returns whether a projection was attempted."""

    if card_id is None:
        return False
    try:
        graph = graph_service_factory()
        if graph is None:
            return False
        sync_factory(session=session, graph=graph).upsert_card(card_id)
        return True
    except Exception:
        logger.debug("Neo4j upsert failed for card %s", card_id, exc_info=True)
        return False


def delete_card(
    card_id: int | None,
    *,
    graph_service_factory: GraphServiceFactory = get_graph_service,
) -> bool:
    if card_id is None:
        return False
    try:
        graph = graph_service_factory()
        if graph is None:
            return False
        graph.delete_zettel(card_id=card_id)
        return True
    except Exception:
        logger.debug("Neo4j delete failed for card %s", card_id, exc_info=True)
        return False


def upsert_links(
    link_ids: list[int],
    session: Session,
    *,
    graph_service_factory: GraphServiceFactory = get_graph_service,
    sync_factory: SyncFactory = ZettelGraphSync,
) -> bool:
    """Project a batch of links to Neo4j. Handles bidirectional pairs."""

    if not link_ids:
        return False
    try:
        graph = graph_service_factory()
        if graph is None:
            return False
        sync = sync_factory(session=session, graph=graph)
        for link_id in link_ids:
            sync.upsert_link(link_id)
        return True
    except Exception:
        logger.debug("Neo4j link-upsert failed (ids=%s)", link_ids, exc_info=True)
        return False


def delete_edges(
    pairs: list[tuple[int, int, str]],
    *,
    graph_service_factory: GraphServiceFactory = get_graph_service,
) -> bool:
    """Delete Neo4j edges given a list of (from_id, to_id, type) tuples."""

    if not pairs:
        return False
    try:
        graph = graph_service_factory()
        if graph is None:
            return False
        for from_id, to_id, type_ in pairs:
            graph.delete_zettel_link(from_id=from_id, to_id=to_id, type_=type_)
        return True
    except Exception:
        logger.debug("Neo4j edge-delete failed", exc_info=True)
        return False
