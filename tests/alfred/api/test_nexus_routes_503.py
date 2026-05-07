"""503 behavior when Neo4j is not configured — no integration marker."""
from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel

from alfred.api.dependencies import get_db_session
from alfred.api.nexus.routes import router as nexus_router
from alfred.core.dependencies import get_graph_service


@pytest.fixture()
def db_session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


@pytest.fixture()
def absent_client(db_session: Session) -> TestClient:
    app = FastAPI()
    app.include_router(nexus_router)
    app.dependency_overrides[get_db_session] = lambda: db_session
    app.dependency_overrides[get_graph_service] = lambda: None
    return TestClient(app)


@pytest.mark.parametrize(
    "method,path,params",
    [
        ("POST", "/api/nexus/sync", None),
        ("GET", "/api/nexus/graph", None),
        ("GET", "/api/nexus/path", {"from_id": 1, "to_id": 2}),
        ("GET", "/api/nexus/bridges", {"limit": 5}),
    ],
)
def test_endpoint_returns_503_when_neo4j_absent(
    absent_client: TestClient, method: str, path: str, params: dict | None
) -> None:
    r = absent_client.request(method, path, params=params)
    assert r.status_code == 503
    assert "Neo4j" in r.json()["detail"]
