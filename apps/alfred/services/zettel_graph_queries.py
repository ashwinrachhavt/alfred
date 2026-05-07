"""Read-only Cypher queries for zettel graph navigation.

Queries run against the Neo4j projection maintained by ZettelGraphSync.
Postgres remains the source of truth; these queries exist because multi-hop
traversal (paths, neighborhoods, bridge detection) is awkward in SQL and
natural in Cypher.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from alfred.services.graph_service import GraphService

logger = logging.getLogger(__name__)

_MAX_PATH_HOPS = 10
_MAX_NEIGHBORHOOD_DEPTH = 3


@dataclass
class ZettelGraphQueries:
    """Read-only traversal queries over the :Zettel subgraph."""

    graph: GraphService

    # ------------------------------------------------------------------
    # Path finding
    # ------------------------------------------------------------------
    def shortest_path(
        self, *, from_id: int, to_id: int, max_hops: int = 6
    ) -> list[int] | None:
        """Return card_ids along the shortest path (inclusive), or None.

        Traverses :LINK edges in either direction. Cap hops to avoid runaway
        queries on dense graphs.
        """
        hops = max(1, min(int(max_hops), _MAX_PATH_HOPS))
        query = f"""
        MATCH (a:Zettel {{card_id: $from_id}}), (b:Zettel {{card_id: $to_id}})
        MATCH p = shortestPath((a)-[:LINK*..{hops}]-(b))
        RETURN [n IN nodes(p) | n.card_id] AS ids
        LIMIT 1
        """
        rows = self.graph._run(
            query, {"from_id": int(from_id), "to_id": int(to_id)}
        )
        if not rows:
            return None
        return [int(x) for x in rows[0]["ids"]]

    # ------------------------------------------------------------------
    # Full graph dump
    # ------------------------------------------------------------------
    def all_nodes_and_edges(self, *, limit: int = 5000) -> dict[str, Any]:
        """Return every :Zettel node and every :LINK edge, up to `limit` nodes.

        The caller owns serialization to API DTOs. Large graphs truncate at
        `limit` nodes (but edges for truncated nodes are still included —
        fast-follow: filter edges by surviving node set).
        """
        node_rows = self.graph._run(
            """
            MATCH (z:Zettel)
            RETURN z.card_id AS card_id, z.title AS title, z.topic AS topic,
                   z.tags AS tags, z.bloom_level AS bloom_level,
                   z.cluster_id AS cluster_id
            LIMIT $limit
            """,
            {"limit": int(limit)},
        )
        edge_rows = self.graph._run(
            """
            MATCH (a:Zettel)-[r:LINK]->(b:Zettel)
            RETURN a.card_id AS source, b.card_id AS target, r.type AS type
            """
        )
        return {"nodes": node_rows, "edges": edge_rows}

    # ------------------------------------------------------------------
    # Neighborhood (ego graph)
    # ------------------------------------------------------------------
    def neighborhood(self, *, card_id: int, depth: int = 1) -> dict[str, Any]:
        """Return nodes and edges within `depth` hops of `card_id`.

        Depth is clamped to [1, _MAX_NEIGHBORHOOD_DEPTH] to bound query cost.

        Note: nodes and edges are fetched in two separate Cypher reads. Each
        result is individually consistent, but a concurrent write between
        the queries may cause an edge to reference a node absent from the
        node list (or vice versa). Callers should tolerate this; the
        projection is already eventually consistent with Postgres.
        """
        depth = max(1, min(int(depth), _MAX_NEIGHBORHOOD_DEPTH))
        node_query = f"""
        MATCH (c:Zettel {{card_id: $card_id}})-[:LINK*1..{depth}]-(n:Zettel)
        WITH collect(DISTINCT c) + collect(DISTINCT n) AS ns
        UNWIND ns AS node
        WITH DISTINCT node
        RETURN collect({{
            card_id: node.card_id,
            title: node.title,
            topic: node.topic,
            tags: node.tags,
            bloom_level: node.bloom_level
        }}) AS nodes
        """
        rows = self.graph._run(node_query, {"card_id": int(card_id)})
        nodes = rows[0]["nodes"] if rows else []

        edge_query = f"""
        MATCH (c:Zettel {{card_id: $card_id}})-[rels:LINK*1..{depth}]-(n:Zettel)
        UNWIND rels AS rel
        WITH DISTINCT startNode(rel) AS s, endNode(rel) AS t, rel.type AS type
        RETURN s.card_id AS source, t.card_id AS target, type
        """
        erows = self.graph._run(edge_query, {"card_id": int(card_id)})
        edges = [
            {
                "source": int(r["source"]),
                "target": int(r["target"]),
                "type": r["type"],
            }
            for r in erows
        ]
        return {"nodes": nodes, "edges": edges}

    # ------------------------------------------------------------------
    # Bridge detection (approximate betweenness via in × out degree)
    # ------------------------------------------------------------------
    def bridges(self, *, limit: int = 10) -> list[dict[str, Any]]:
        """Return nodes with highest in-degree × out-degree product.

        This is a cheap proxy for betweenness centrality that works without
        the Graph Data Science plugin. Only returns nodes with both inbound
        and outbound edges (score > 0).
        """
        query = """
        MATCH (z:Zettel)
        OPTIONAL MATCH (z)-[:LINK]->(out:Zettel)
        WITH z, count(DISTINCT out) AS out_deg
        OPTIONAL MATCH (inn:Zettel)-[:LINK]->(z)
        WITH z, out_deg, count(DISTINCT inn) AS in_deg
        WITH z, out_deg * in_deg AS score
        WHERE score > 0
        RETURN z.card_id AS card_id, z.title AS title, score
        ORDER BY score DESC
        LIMIT $limit
        """
        rows = self.graph._run(query, {"limit": int(limit)})
        return [
            {
                "card_id": int(r["card_id"]),
                "title": r["title"],
                "score": int(r["score"]),
            }
            for r in rows
        ]
