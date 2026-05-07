"""Zettel-specific helpers on GraphService (requires Neo4j)."""
from __future__ import annotations

import os
import pytest

pytestmark = pytest.mark.integration

pytest.importorskip("neo4j")

from alfred.services.graph_service import GraphService


@pytest.fixture
def gs():
    uri = os.environ.get("NEO4J_URI")
    if not uri:
        pytest.skip("NEO4J_URI not set")
    svc = GraphService(
        uri=uri,
        user=os.environ.get("NEO4J_USER", "neo4j"),
        password=os.environ.get("NEO4J_PASSWORD", "neo4j_password"),
    )
    svc._run("MATCH (z:Zettel) DETACH DELETE z")
    yield svc
    svc._run("MATCH (z:Zettel) DETACH DELETE z")
    svc.close()


def test_upsert_zettel_creates_node(gs):
    gs.upsert_zettel(
        card_id=1, title="Stoicism", topic="philosophy",
        tags=["classic"], bloom_level=3, cluster_id=0,
    )
    rows = gs._run("MATCH (z:Zettel {card_id: 1}) RETURN z.title AS title")
    assert rows == [{"title": "Stoicism"}]


def test_upsert_zettel_is_idempotent(gs):
    gs.upsert_zettel(card_id=1, title="A", topic=None, tags=[], bloom_level=1, cluster_id=None)
    gs.upsert_zettel(card_id=1, title="B", topic=None, tags=[], bloom_level=1, cluster_id=None)
    rows = gs._run("MATCH (z:Zettel {card_id: 1}) RETURN count(z) AS n")
    assert rows[0]["n"] == 1


def test_link_zettels_creates_typed_edge(gs):
    gs.upsert_zettel(card_id=1, title="A", topic=None, tags=[], bloom_level=1, cluster_id=None)
    gs.upsert_zettel(card_id=2, title="B", topic=None, tags=[], bloom_level=1, cluster_id=None)
    gs.link_zettels(from_id=1, to_id=2, type_="extends", bidirectional=False)
    rows = gs._run(
        "MATCH (a:Zettel {card_id: 1})-[r:LINK {type: 'extends'}]->(b:Zettel {card_id: 2}) RETURN count(r) AS n"
    )
    assert rows[0]["n"] == 1


def test_delete_zettel_removes_node_and_edges(gs):
    gs.upsert_zettel(card_id=1, title="A", topic=None, tags=[], bloom_level=1, cluster_id=None)
    gs.upsert_zettel(card_id=2, title="B", topic=None, tags=[], bloom_level=1, cluster_id=None)
    gs.link_zettels(from_id=1, to_id=2, type_="ref", bidirectional=False)
    gs.delete_zettel(card_id=1)
    rows = gs._run("MATCH (z:Zettel {card_id: 1}) RETURN count(z) AS n")
    assert rows[0]["n"] == 0
