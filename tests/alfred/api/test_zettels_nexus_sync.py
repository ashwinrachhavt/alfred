"""Confirm zettel HTTP mutations propagate to Neo4j projection."""
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
from alfred.api.zettels import router as zettels_router
from alfred.core.dependencies import get_graph_service
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
    get_graph_service.cache_clear()
    svc = GraphService(
        uri=os.environ["NEO4J_URI"],
        user=os.environ.get("NEO4J_USER", "neo4j"),
        password=os.environ.get("NEO4J_PASSWORD", "neo4j_password"),
    )
    svc.wipe_zettel_subgraph()
    try:
        yield svc
    finally:
        svc.wipe_zettel_subgraph()
        svc.close()
        get_graph_service.cache_clear()


@pytest.fixture()
def client(db_session: Session, gs: GraphService) -> TestClient:
    app = FastAPI()
    app.include_router(zettels_router)
    app.dependency_overrides[get_db_session] = lambda: db_session
    # NOTE: dependency_overrides[get_graph_service] has no effect here —
    # the Neo4j hooks call get_graph_service() directly, not via Depends.
    # The lru_cache is cleared in the `gs` fixture so the real
    # get_graph_service() builds a driver pointing at the same NEO4J_URI
    # as our test fixture. The `gs` fixture exists purely to manage the
    # Zettel subgraph lifecycle, not to inject a driver.
    return TestClient(app)


def test_create_card_projects_into_neo4j(client: TestClient, gs: GraphService) -> None:
    r = client.post("/api/zettels/cards", json={"title": "Hello", "tags": []})
    assert r.status_code == 201
    card_id = r.json()["id"]
    rows = gs._run(
        "MATCH (z:Zettel {card_id: $id}) RETURN z.title AS t", {"id": card_id}
    )
    assert rows and rows[0]["t"] == "Hello"


def test_update_card_refreshes_projection(client: TestClient, gs: GraphService) -> None:
    r = client.post("/api/zettels/cards", json={"title": "Before", "tags": []})
    card_id = r.json()["id"]
    client.patch(f"/api/zettels/cards/{card_id}", json={"title": "After"})
    rows = gs._run(
        "MATCH (z:Zettel {card_id: $id}) RETURN z.title AS t", {"id": card_id}
    )
    assert rows[0]["t"] == "After"


def test_delete_card_removes_from_neo4j(client: TestClient, gs: GraphService) -> None:
    r = client.post("/api/zettels/cards", json={"title": "Gone", "tags": []})
    card_id = r.json()["id"]
    client.delete(f"/api/zettels/cards/{card_id}")
    rows = gs._run(
        "MATCH (z:Zettel {card_id: $id}) RETURN count(z) AS n", {"id": card_id}
    )
    assert rows[0]["n"] == 0


def test_link_creates_edge_in_neo4j(client: TestClient, gs: GraphService) -> None:
    a = client.post("/api/zettels/cards", json={"title": "A", "tags": []}).json()
    b = client.post("/api/zettels/cards", json={"title": "B", "tags": []}).json()
    r = client.post(
        f"/api/zettels/cards/{a['id']}/links",
        json={"to_card_id": b["id"], "type": "ref", "bidirectional": False},
    )
    assert r.status_code == 201
    rows = gs._run(
        """
        MATCH (a:Zettel {card_id: $from})-[r:LINK {type: 'ref'}]->(b:Zettel {card_id: $to})
        RETURN count(r) AS n
        """,
        {"from": a["id"], "to": b["id"]},
    )
    assert rows[0]["n"] == 1


def test_delete_link_removes_edge_from_neo4j(client: TestClient, gs: GraphService) -> None:
    a = client.post("/api/zettels/cards", json={"title": "A", "tags": []}).json()
    b = client.post("/api/zettels/cards", json={"title": "B", "tags": []}).json()
    link_list = client.post(
        f"/api/zettels/cards/{a['id']}/links",
        json={"to_card_id": b["id"], "type": "ref", "bidirectional": False},
    ).json()
    link_id = link_list[0]["id"]
    client.delete(f"/api/zettels/links/{link_id}")
    rows = gs._run(
        "MATCH (a:Zettel {card_id: $from})-[r:LINK]->(b:Zettel {card_id: $to}) RETURN count(r) AS n",
        {"from": a["id"], "to": b["id"]},
    )
    assert rows[0]["n"] == 0


def test_create_card_returns_201_when_neo4j_absent(db_session: Session, monkeypatch) -> None:
    """Silent-failure contract: HTTP still succeeds when Neo4j is unavailable."""
    import alfred.core.dependencies as core_deps

    core_deps.get_graph_service.cache_clear()
    monkeypatch.setattr(core_deps, "get_graph_service", lambda: None)

    app = FastAPI()
    app.include_router(zettels_router)
    app.dependency_overrides[get_db_session] = lambda: db_session
    absent_client = TestClient(app)

    r = absent_client.post("/api/zettels/cards", json={"title": "NoNeo4j", "tags": []})
    assert r.status_code == 201
