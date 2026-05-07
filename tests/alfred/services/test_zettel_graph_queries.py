"""Read-only Cypher queries for zettel graph navigation."""
from __future__ import annotations

import os

import pytest

pytestmark = pytest.mark.integration

pytest.importorskip("neo4j")

from alfred.services.graph_service import GraphService
from alfred.services.zettel_graph_queries import ZettelGraphQueries


@pytest.fixture()
def queries():
    if not os.environ.get("NEO4J_URI"):
        pytest.skip("NEO4J_URI not set")
    gs = GraphService(
        uri=os.environ["NEO4J_URI"],
        user=os.environ.get("NEO4J_USER", "neo4j"),
        password=os.environ.get("NEO4J_PASSWORD", "neo4j_password"),
    )
    gs.wipe_zettel_subgraph()
    # Diamond graph: 1 -> 2 -> 4, 1 -> 3 -> 4
    for i in range(1, 5):
        gs.upsert_zettel(
            card_id=i, title=f"N{i}", topic=None, tags=[],
            bloom_level=1, cluster_id=None,
        )
    gs.link_zettels(from_id=1, to_id=2, type_="ref", bidirectional=False)
    gs.link_zettels(from_id=2, to_id=4, type_="ref", bidirectional=False)
    gs.link_zettels(from_id=1, to_id=3, type_="ref", bidirectional=False)
    gs.link_zettels(from_id=3, to_id=4, type_="ref", bidirectional=False)
    q = ZettelGraphQueries(graph=gs)
    yield q
    gs.wipe_zettel_subgraph()
    gs.close()


def test_shortest_path_returns_ids_in_order(queries):
    path = queries.shortest_path(from_id=1, to_id=4)
    assert path is not None
    assert path[0] == 1 and path[-1] == 4
    assert len(path) == 3  # diamond: 1 -> {2 or 3} -> 4


def test_shortest_path_returns_none_when_disconnected(queries):
    assert queries.shortest_path(from_id=1, to_id=999) is None


def test_neighborhood_returns_nodes_within_depth(queries):
    nbrs = queries.neighborhood(card_id=1, depth=1)
    ids = {n["card_id"] for n in nbrs["nodes"]}
    assert ids == {1, 2, 3}


def test_neighborhood_returns_edges_for_hops(queries):
    nbrs = queries.neighborhood(card_id=1, depth=1)
    # Should include both outgoing edges 1->2 and 1->3
    pairs = {(e["source"], e["target"]) for e in nbrs["edges"]}
    assert (1, 2) in pairs
    assert (1, 3) in pairs


def test_bridges_returns_high_score_nodes(queries):
    result = queries.bridges(limit=5)
    assert len(result) >= 1
    # In a diamond, nodes 2 and 3 each have in_deg=1, out_deg=1 => score=1
    # Node 1 has in_deg=0 (score=0) so it's filtered
    # Node 4 has out_deg=0 (score=0) so it's filtered
    scores = {b["card_id"]: b["score"] for b in result}
    assert scores.get(2, 0) == 1
    assert scores.get(3, 0) == 1
    # Confirm filtered nodes absent
    assert 1 not in scores
    assert 4 not in scores


def test_bridges_honours_limit(queries):
    result = queries.bridges(limit=1)
    assert len(result) <= 1
