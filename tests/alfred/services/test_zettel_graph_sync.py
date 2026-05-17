"""Zettel → Neo4j projection sync."""
from __future__ import annotations

import os

import pytest

pytestmark = pytest.mark.integration

pytest.importorskip("neo4j")

from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel

from alfred.models.zettel import ZettelCard, ZettelLink
from alfred.services.graph_service import GraphService
from alfred.services.zettel_graph_sync import ZettelGraphSync


@pytest.fixture()
def db_session():
    if not os.environ.get("NEO4J_URI"):
        pytest.skip("NEO4J_URI not set")
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


@pytest.fixture()
def gs():
    if not os.environ.get("NEO4J_URI"):
        pytest.skip("NEO4J_URI not set")
    svc = GraphService(
        uri=os.environ["NEO4J_URI"],
        user=os.environ.get("NEO4J_USER", "neo4j"),
        password=os.environ.get("NEO4J_PASSWORD", "neo4j_password"),
    )
    svc._run("MATCH (z:Zettel) DETACH DELETE z")
    yield svc
    svc._run("MATCH (z:Zettel) DETACH DELETE z")
    svc.close()


def test_full_rebuild_syncs_all_active_cards(db_session: Session, gs):
    a = ZettelCard(title="A", status="active", bloom_level=1, bloom_source="backfill")
    b = ZettelCard(title="B", status="active", bloom_level=2, bloom_source="backfill")
    arch = ZettelCard(title="Old", status="archived", bloom_level=1, bloom_source="backfill")
    db_session.add_all([a, b, arch])
    db_session.commit()
    db_session.refresh(a)
    db_session.refresh(b)
    link = ZettelLink(from_card_id=a.id, to_card_id=b.id, type="reference", bidirectional=False)
    db_session.add(link)
    db_session.commit()

    sync = ZettelGraphSync(session=db_session, graph=gs)
    result = sync.full_rebuild()

    assert result["nodes_synced"] == 2
    assert result["edges_synced"] == 1
    rows = gs._run("MATCH (z:Zettel) RETURN count(z) AS n")
    assert rows[0]["n"] == 2
    rows = gs._run("MATCH ()-[r:LINK]->() RETURN count(r) AS n")
    assert rows[0]["n"] == 1


def test_upsert_card_projects_single_node(db_session: Session, gs):
    card = ZettelCard(title="A", status="active", bloom_level=1, bloom_source="backfill")
    db_session.add(card)
    db_session.commit()
    db_session.refresh(card)
    sync = ZettelGraphSync(session=db_session, graph=gs)
    sync.upsert_card(card.id)
    rows = gs._run("MATCH (z:Zettel {card_id: $id}) RETURN z.title AS t", {"id": card.id})
    assert rows[0]["t"] == "A"


def test_delete_card_removes_projection(db_session: Session, gs):
    card = ZettelCard(title="Gone", status="active", bloom_level=1, bloom_source="backfill")
    db_session.add(card)
    db_session.commit()
    db_session.refresh(card)
    sync = ZettelGraphSync(session=db_session, graph=gs)
    sync.upsert_card(card.id)
    sync.delete_card(card.id)
    rows = gs._run("MATCH (z:Zettel {card_id: $id}) RETURN count(z) AS n", {"id": card.id})
    assert rows[0]["n"] == 0


def test_upsert_card_with_archived_status_removes_projection(db_session: Session, gs):
    card = ZettelCard(title="A", status="active", bloom_level=1, bloom_source="backfill")
    db_session.add(card)
    db_session.commit()
    db_session.refresh(card)
    sync = ZettelGraphSync(session=db_session, graph=gs)
    sync.upsert_card(card.id)
    # Now archive it and re-sync
    card.status = "archived"
    db_session.add(card)
    db_session.commit()
    sync.upsert_card(card.id)
    rows = gs._run("MATCH (z:Zettel {card_id: $id}) RETURN count(z) AS n", {"id": card.id})
    assert rows[0]["n"] == 0
