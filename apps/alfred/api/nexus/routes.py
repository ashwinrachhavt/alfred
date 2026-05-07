"""Nexus graph endpoints — GitNexus-style zettel graph view.

Endpoints:
    POST /api/nexus/sync     — full rebuild of the Neo4j zettel projection
    GET  /api/nexus/graph    — entire graph (nodes + edges) for rendering
    GET  /api/nexus/path     — shortest path between two cards
    GET  /api/nexus/bridges  — top-N bridge-like nodes by in*out degree
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query
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
    graph = _require_graph(gs)
    sync = ZettelGraphSync(session=session, graph=graph)
    result = sync.full_rebuild()
    logger.info(
        "nexus sync complete: %d nodes, %d edges",
        result["nodes_synced"],
        result["edges_synced"],
    )
    return NexusSyncResult(**result)


@router.get("/graph", response_model=NexusGraph)
def get_graph(
    limit: int = Query(5000, ge=1, le=50000, description="Max nodes to return"),
    gs: GraphService | None = Depends(get_graph_service),
) -> NexusGraph:
    """Full graph dump for client-side rendering (Sigma.js / ForceGraph)."""
    graph = _require_graph(gs)
    q = ZettelGraphQueries(graph=graph)
    result = q.all_nodes_and_edges(limit=limit)
    nodes = [
        NexusNode(
            card_id=int(r["card_id"]),
            title=r["title"] or "",
            topic=r.get("topic"),
            tags=list(r.get("tags") or []),
            bloom_level=int(r["bloom_level"]) if r.get("bloom_level") is not None else 1,
            cluster_id=r.get("cluster_id"),
        )
        for r in result["nodes"]
    ]
    edges = [
        NexusEdge(
            source=int(r["source"]),
            target=int(r["target"]),
            type=r["type"],
        )
        for r in result["edges"]
    ]
    return NexusGraph(nodes=nodes, edges=edges)


@router.get("/path", response_model=NexusPath)
def find_path(
    from_id: int = Query(..., ge=1),
    to_id: int = Query(..., ge=1),
    max_hops: int = Query(6, ge=1, le=10),
    gs: GraphService | None = Depends(get_graph_service),
) -> NexusPath:
    """Return the shortest path between two cards as an ordered list of ids."""
    graph = _require_graph(gs)
    q = ZettelGraphQueries(graph=graph)
    path = q.shortest_path(from_id=from_id, to_id=to_id, max_hops=max_hops)
    if path is None:
        raise HTTPException(status_code=404, detail="No path found")
    return NexusPath(card_ids=path)


@router.get("/bridges", response_model=list[NexusBridge])
def find_bridges(
    limit: int = Query(10, ge=1, le=500),
    gs: GraphService | None = Depends(get_graph_service),
) -> list[NexusBridge]:
    """Top-N bridge-like nodes by in-degree × out-degree."""
    graph = _require_graph(gs)
    q = ZettelGraphQueries(graph=graph)
    return [NexusBridge(**r) for r in q.bridges(limit=limit)]
