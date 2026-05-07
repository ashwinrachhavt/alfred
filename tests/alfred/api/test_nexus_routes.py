"""Integration tests for /api/nexus/* routes."""
from __future__ import annotations

import os

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel

pytestmark = pytest.mark.integration

pytest.importorskip("neo4j")

from alfred.api.dependencies import get_db_session
from alfred.api.nexus.routes import router as nexus_router
from alfred.core.dependencies import get_graph_service
from alfred.models.zettel import ZettelCard, ZettelLink
from alfred.services.graph_service import GraphService


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
    svc.wipe_zettel_subgraph()
    yield svc
    svc.wipe_zettel_subgraph()
    svc.close()


@pytest.fixture()
def client(db_session: Session, gs: GraphService) -> TestClient:
    app = FastAPI()
    app.include_router(nexus_router)
    app.dependency_overrides[get_db_session] = lambda: db_session
    app.dependency_overrides[get_graph_service] = lambda: gs
    return TestClient(app)


def test_sync_endpoint_returns_counts(client: TestClient, db_session: Session) -> None:
    card = ZettelCard(
        title="Seed", status="active", bloom_level=1, bloom_source="backfill"
    )
    db_session.add(card)
    db_session.commit()
    r = client.post("/api/nexus/sync")
    assert r.status_code == 200
    body = r.json()
    assert body["nodes_synced"] == 1
    assert body["edges_synced"] == 0


def test_graph_endpoint_returns_nodes_and_edges(
    client: TestClient, db_session: Session
) -> None:
    a = ZettelCard(title="A", status="active", bloom_level=1, bloom_source="backfill")
    b = ZettelCard(title="B", status="active", bloom_level=1, bloom_source="backfill")
    db_session.add_all([a, b])
    db_session.commit()
    db_session.refresh(a)
    db_session.refresh(b)
    db_session.add(
        ZettelLink(
            from_card_id=a.id, to_card_id=b.id, type="ref", bidirectional=False
        )
    )
    db_session.commit()
    client.post("/api/nexus/sync")

    r = client.get("/api/nexus/graph")
    assert r.status_code == 200
    body = r.json()
    assert len(body["nodes"]) == 2
    assert len(body["edges"]) == 1
    assert body["edges"][0]["type"] == "ref"


def test_path_endpoint_returns_404_when_disconnected(
    client: TestClient, db_session: Session
) -> None:
    client.post("/api/nexus/sync")
    r = client.get("/api/nexus/path", params={"from_id": 99991, "to_id": 99992})
    assert r.status_code == 404


def test_path_endpoint_returns_ids_when_connected(
    client: TestClient, db_session: Session
) -> None:
    a = ZettelCard(title="A", status="active", bloom_level=1, bloom_source="backfill")
    b = ZettelCard(title="B", status="active", bloom_level=1, bloom_source="backfill")
    db_session.add_all([a, b])
    db_session.commit()
    db_session.refresh(a)
    db_session.refresh(b)
    db_session.add(
        ZettelLink(
            from_card_id=a.id, to_card_id=b.id, type="ref", bidirectional=False
        )
    )
    db_session.commit()
    client.post("/api/nexus/sync")

    r = client.get("/api/nexus/path", params={"from_id": a.id, "to_id": b.id})
    assert r.status_code == 200
    body = r.json()
    assert body["card_ids"] == [a.id, b.id]


def test_bridges_endpoint_returns_list(
    client: TestClient, db_session: Session
) -> None:
    client.post("/api/nexus/sync")
    r = client.get("/api/nexus/bridges", params={"limit": 5})
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_sync_returns_503_when_neo4j_absent(db_session: Session) -> None:
    app = FastAPI()
    app.include_router(nexus_router)
    app.dependency_overrides[get_db_session] = lambda: db_session
    app.dependency_overrides[get_graph_service] = lambda: None
    absent_client = TestClient(app)
    r = absent_client.post("/api/nexus/sync")
    assert r.status_code == 503
