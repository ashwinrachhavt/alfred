"""Route tests for manual zettel link create / patch / list-types."""

from __future__ import annotations

from collections.abc import Generator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, select

from alfred.api.dependencies import get_db_session
from alfred.api.zettels import routes as zettel_routes
from alfred.api.zettels.routes import router as zettels_router
from alfred.models.zettel import ZettelLink
from alfred.services.zettelkasten_service import ZettelkastenService


@pytest.fixture()
def session() -> Generator[Session, None, None]:
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


@pytest.fixture()
def client(session: Session, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    app = FastAPI()
    app.include_router(zettels_router)
    app.dependency_overrides[get_db_session] = lambda: session

    monkeypatch.setattr(zettel_routes, "_cache_get", lambda _key: None)
    monkeypatch.setattr(zettel_routes, "_cache_set", lambda _k, _v: None)
    monkeypatch.setattr(zettel_routes, "_invalidate_graph_cache", lambda: None)
    monkeypatch.setattr(zettel_routes, "get_redis_client", lambda: None)
    return TestClient(app)


def _mk_pair(session: Session) -> tuple[int, int]:
    svc = ZettelkastenService(session)
    a = svc.create_card(title="A")
    b = svc.create_card(title="B")
    return a.id or 0, b.id or 0


def test_create_link_rejects_self_link(client: TestClient, session: Session) -> None:
    a, _ = _mk_pair(session)
    resp = client.post(f"/api/zettels/cards/{a}/links", json={"to_card_id": a})
    assert resp.status_code == 400
    assert "itself" in resp.json()["detail"].lower()


def test_create_link_rejects_empty_type(client: TestClient, session: Session) -> None:
    a, b = _mk_pair(session)
    resp = client.post(
        f"/api/zettels/cards/{a}/links",
        json={"to_card_id": b, "type": "   "},
    )
    assert resp.status_code == 400


def test_create_link_normalizes_type(client: TestClient, session: Session) -> None:
    a, b = _mk_pair(session)
    resp = client.post(
        f"/api/zettels/cards/{a}/links",
        json={"to_card_id": b, "type": "  Supports  ", "bidirectional": False},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert len(body) == 1
    assert body[0]["type"] == "supports"


def test_patch_link_updates_type_and_context(client: TestClient, session: Session) -> None:
    a, b = _mk_pair(session)
    svc = ZettelkastenService(session)
    link = svc.create_link(
        from_card_id=a, to_card_id=b, type="related", bidirectional=False
    )[0]
    resp = client.patch(
        f"/api/zettels/links/{link.id}",
        json={"type": "Supports", "context": "X implies Y"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["type"] == "supports"
    assert body["context"] == "X implies Y"


def test_patch_link_not_found_returns_404(client: TestClient) -> None:
    resp = client.patch("/api/zettels/links/9999", json={"type": "related"})
    assert resp.status_code == 404


def test_patch_link_rejects_empty_type(client: TestClient, session: Session) -> None:
    a, b = _mk_pair(session)
    svc = ZettelkastenService(session)
    link = svc.create_link(
        from_card_id=a, to_card_id=b, type="related", bidirectional=False
    )[0]
    resp = client.patch(f"/api/zettels/links/{link.id}", json={"type": "   "})
    assert resp.status_code == 400


def test_patch_link_toggles_bidirectional(client: TestClient, session: Session) -> None:
    a, b = _mk_pair(session)
    svc = ZettelkastenService(session)
    link = svc.create_link(
        from_card_id=a, to_card_id=b, type="related", bidirectional=False
    )[0]

    resp = client.patch(f"/api/zettels/links/{link.id}", json={"bidirectional": True})
    assert resp.status_code == 200
    assert resp.json()["bidirectional"] is True
    rows = list(session.exec(select(ZettelLink)))
    assert len(rows) == 2


def test_get_link_types_returns_distinct_with_counts(
    client: TestClient, session: Session
) -> None:
    a, b = _mk_pair(session)
    svc = ZettelkastenService(session)
    svc.create_link(from_card_id=a, to_card_id=b, type="related", bidirectional=True)
    svc.create_link(from_card_id=a, to_card_id=b, type="supports", bidirectional=False)

    resp = client.get("/api/zettels/link-types")
    assert resp.status_code == 200
    body = resp.json()
    types = [row["type"] for row in body]
    counts = {row["type"]: row["count"] for row in body}
    assert types.index("related") < types.index("supports")
    assert counts["related"] == 2
    assert counts["supports"] == 1
