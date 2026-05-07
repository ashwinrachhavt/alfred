"""Nexus graph endpoints — GitNexus-style zettel graph view.

Endpoints:
    POST /api/nexus/sync     — full rebuild of the Neo4j zettel projection
    GET  /api/nexus/graph    — entire graph (nodes + edges) for rendering
    GET  /api/nexus/path     — shortest path between two cards
    GET  /api/nexus/bridges  — top-N bridge-like nodes by in*out degree
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from alfred.api.dependencies import get_db_session
from alfred.core.dependencies import get_graph_service
from alfred.schemas.nexus import (
    NexusBridge,
    NexusEdge,
    NexusGraph,
    NexusNode,
    NexusPath,
    NexusSyncResult,
)
from alfred.services.graph_service import GraphService
from alfred.services.zettel_graph_queries import ZettelGraphQueries
from alfred.services.zettel_graph_sync import ZettelGraphSync

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/nexus", tags=["nexus"])


def _require_graph(gs: GraphService | None) -> GraphService:
    """Raise 503 when Neo4j isn't configured; Postgres-only mode is fine elsewhere."""
    if gs is None:
        raise HTTPException(
            status_code=503,
            detail="Neo4j is not configured. Set NEO4J_URI/NEO4J_USER/NEO4J_PASSWORD.",
        )
    return gs


@router.post("/sync", response_model=NexusSyncResult)
def sync_graph(
    session: Session = Depends(get_db_session),
    gs: GraphService | None = Depends(get_graph_service),
) -> NexusSyncResult:
    """Rebuild the Neo4j :Zettel subgraph from Postgres."""
    gs = _require_graph(gs)
    sync = ZettelGraphSync(session=session, graph=gs)
    return NexusSyncResult(**sync.full_rebuild())


@router.get("/graph", response_model=NexusGraph)
def get_graph(
    gs: GraphService | None = Depends(get_graph_service),
) -> NexusGraph:
    """Full graph dump for client-side rendering (Sigma.js / ForceGraph)."""
    gs = _require_graph(gs)
    rows = gs._run(
        """
        MATCH (z:Zettel)
        RETURN z.card_id AS card_id, z.title AS title, z.topic AS topic,
               z.tags AS tags, z.bloom_level AS bloom_level, z.cluster_id AS cluster_id
        """
    )
    nodes = [
        NexusNode(
            card_id=int(r["card_id"]),
            title=r["title"] or "",
            topic=r.get("topic"),
            tags=list(r.get("tags") or []),
            bloom_level=int(r.get("bloom_level") or 1),
            cluster_id=r.get("cluster_id"),
        )
        for r in rows
    ]
    erows = gs._run(
        """
        MATCH (a:Zettel)-[r:LINK]->(b:Zettel)
        RETURN a.card_id AS source, b.card_id AS target, r.type AS type
        """
    )
    edges = [
        NexusEdge(
            source=int(r["source"]),
            target=int(r["target"]),
            type=r["type"],
        )
        for r in erows
    ]
    return NexusGraph(nodes=nodes, edges=edges)


@router.get("/path", response_model=NexusPath)
def find_path(
    from_id: int,
    to_id: int,
    max_hops: int = 6,
    gs: GraphService | None = Depends(get_graph_service),
) -> NexusPath:
    """Return the shortest path between two cards as an ordered list of ids."""
    gs = _require_graph(gs)
    q = ZettelGraphQueries(graph=gs)
    path = q.shortest_path(from_id=from_id, to_id=to_id, max_hops=max_hops)
    if path is None:
        raise HTTPException(status_code=404, detail="No path found")
    return NexusPath(card_ids=path)


@router.get("/bridges", response_model=list[NexusBridge])
def find_bridges(
    limit: int = 10,
    gs: GraphService | None = Depends(get_graph_service),
) -> list[NexusBridge]:
    """Top-N bridge-like nodes by in-degree × out-degree."""
    gs = _require_graph(gs)
    q = ZettelGraphQueries(graph=gs)
    return [NexusBridge(**r) for r in q.bridges(limit=limit)]
