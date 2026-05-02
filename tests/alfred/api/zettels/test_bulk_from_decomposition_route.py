"""Tests for POST /api/zettels/bulk-from-decomposition (T7)."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, select

from alfred.api.dependencies import get_db_session
from alfred.api.zettels.routes import router as zettels_router
from alfred.core.utils import utcnow_naive
from alfred.models.zettel import ZettelCard, ZettelLink, ZettelSession
from alfred.services.session_service import SessionService


@pytest.fixture()
def db_session() -> Session:
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


@pytest.fixture(autouse=True)
def _stub_embeddings(monkeypatch: pytest.MonkeyPatch):
    """Stop every ZettelkastenService instance from hitting OpenAI/Qdrant.

    We default to a no-op; individual tests can override this fixture.
    """
    import alfred.services.zettelkasten_service as zk_mod

    original_init = zk_mod.ZettelkastenService.__init__

    def _patched_init(self, session):
        original_init(self, session)
        self.ensure_embedding = MagicMock(side_effect=lambda card: card)

    monkeypatch.setattr(zk_mod.ZettelkastenService, "__init__", _patched_init)


@pytest.fixture()
def client(db_session: Session) -> TestClient:
    app = FastAPI()
    app.include_router(zettels_router)
    app.dependency_overrides[get_db_session] = lambda: db_session
    return TestClient(app)


def _candidate(
    title: str,
    *,
    bloom_level: int = 2,
    links: list[int] | None = None,
    tags: list[str] | None = None,
) -> dict:
    return {
        "title": title,
        "content": f"Content for {title}.",
        "bloom_level": bloom_level,
        "tags": tags or [],
        "links_to_siblings": links or [],
    }


# ---------------------------------------------------------------------------
# Happy paths
# ---------------------------------------------------------------------------


def test_bulk_creates_all_cards_with_session_id_and_source_url(
    client: TestClient, db_session: Session
) -> None:
    sess = ZettelSession(title="sitting")
    db_session.add(sess)
    db_session.commit()
    db_session.refresh(sess)

    payload = {
        "session_id": sess.id,
        "shared_topic": "networking",
        "source_url": "http://example.com/article",
        "candidates": [
            _candidate("First atom", bloom_level=2),
            _candidate("Second atom", bloom_level=3),
            _candidate("Third atom", bloom_level=4),
        ],
    }
    resp = client.post("/api/zettels/bulk-from-decomposition", json=payload)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert len(body["created_card_ids"]) == 3
    assert body["link_count"] == 0

    rows = list(
        db_session.exec(select(ZettelCard).where(ZettelCard.id.in_(body["created_card_ids"])))
    )
    by_id = {c.id: c for c in rows}
    for i, cid in enumerate(body["created_card_ids"]):
        c = by_id[cid]
        assert c.session_id == sess.id
        assert c.source_url == "http://example.com/article"
        assert c.topic == "networking"
        assert c.bloom_source == "ai_inferred"
        assert c.bloom_level == payload["candidates"][i]["bloom_level"]


def test_bulk_creates_sibling_links(client: TestClient, db_session: Session) -> None:
    payload = {
        "candidates": [
            _candidate("A", links=[1]),
            _candidate("B", links=[0, 2]),
            _candidate("C", links=[]),
        ],
    }
    resp = client.post("/api/zettels/bulk-from-decomposition", json=payload)
    assert resp.status_code == 200
    body = resp.json()
    card_ids = body["created_card_ids"]
    assert len(card_ids) == 3
    # create_link(bidirectional=True) is called 3 times total:
    #   A->B (dedup of B->A via bidirectional flag), B->A, B->C.
    # Actually: A.links=[1] => 1 call, B.links=[0,2] => 2 calls. Total 3.
    assert body["link_count"] == 3

    links = list(db_session.exec(select(ZettelLink)))
    pairs = {(link.from_card_id, link.to_card_id) for link in links}
    assert (card_ids[0], card_ids[1]) in pairs
    assert (card_ids[1], card_ids[0]) in pairs
    assert (card_ids[1], card_ids[2]) in pairs
    assert (card_ids[2], card_ids[1]) in pairs
    for link in links:
        assert link.type == "decomposition_sibling"
        assert link.bidirectional is True


def test_bulk_silently_drops_invalid_sibling_indexes(
    client: TestClient, db_session: Session
) -> None:
    payload = {
        "candidates": [
            _candidate("A", links=[99, 0, -1, 1]),
            _candidate("B"),
        ],
    }
    resp = client.post("/api/zettels/bulk-from-decomposition", json=payload)
    assert resp.status_code == 200
    body = resp.json()
    assert body["link_count"] == 1
    card_ids = body["created_card_ids"]
    links = list(db_session.exec(select(ZettelLink)))
    pairs = {(link.from_card_id, link.to_card_id) for link in links}
    assert pairs == {(card_ids[0], card_ids[1]), (card_ids[1], card_ids[0])}


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def test_bulk_rejects_empty_candidates(client: TestClient) -> None:
    resp = client.post("/api/zettels/bulk-from-decomposition", json={"candidates": []})
    assert resp.status_code == 400
    assert "No candidates provided" in resp.json()["detail"]


def test_bulk_rejects_too_many_candidates(client: TestClient) -> None:
    payload = {"candidates": [_candidate(f"C{i}") for i in range(51)]}
    resp = client.post("/api/zettels/bulk-from-decomposition", json=payload)
    assert resp.status_code == 400
    assert "Maximum" in resp.json()["detail"]


def test_bulk_rejects_ended_session(client: TestClient, db_session: Session) -> None:
    sess = ZettelSession(title="bye")
    db_session.add(sess)
    db_session.commit()
    db_session.refresh(sess)
    SessionService(db_session).end(sess.id)
    db_session.expire_all()
    refreshed = db_session.get(ZettelSession, sess.id)
    assert refreshed is not None and refreshed.ended_at is not None

    payload = {
        "session_id": sess.id,
        "candidates": [_candidate("A")],
    }
    resp = client.post("/api/zettels/bulk-from-decomposition", json=payload)
    assert resp.status_code == 400
    assert "ended" in resp.json()["detail"].lower()


# ---------------------------------------------------------------------------
# Regression invariants
# ---------------------------------------------------------------------------


def test_bulk_from_decomposition_cards_appear_as_link_candidates_for_each_other(
    client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Iron-rule regression: every created card must be pushed through
    ensure_embedding so Qdrant sees it and they can auto-link later (T2)."""
    synced_card_ids: list[int] = []

    import alfred.services.zettelkasten_service as zk_mod

    original_init = zk_mod.ZettelkastenService.__init__

    def _recording_init(self, session):
        original_init(self, session)

        def _record(card):
            if card.id is not None:
                synced_card_ids.append(card.id)
            return card

        self.ensure_embedding = _record

    monkeypatch.setattr(zk_mod.ZettelkastenService, "__init__", _recording_init)

    payload = {
        "candidates": [_candidate("A"), _candidate("B"), _candidate("C")],
    }
    resp = client.post("/api/zettels/bulk-from-decomposition", json=payload)
    assert resp.status_code == 200
    body = resp.json()
    card_ids = body["created_card_ids"]
    assert len(card_ids) == 3
    assert set(synced_card_ids) == set(card_ids)


def test_bulk_replaces_legacy_bulk_route_contract(client: TestClient) -> None:
    """Iron-rule regression: the new endpoint does NOT collide with the
    legacy /api/zettels/cards/bulk (still used until T11 rips out the
    decomposition dialog). Both paths respond independently.
    """
    legacy_resp = client.post(
        "/api/zettels/cards/bulk",
        json=[{"title": "legacy card"}],
    )
    assert legacy_resp.status_code in (200, 201)

    new_resp = client.post(
        "/api/zettels/bulk-from-decomposition",
        json={"candidates": [_candidate("new card")]},
    )
    assert new_resp.status_code == 200
    assert len(new_resp.json()["created_card_ids"]) == 1


def test_bulk_sets_ai_inferred_bloom_source(client: TestClient, db_session: Session) -> None:
    """Sanity: user-adjusted bloom_level passes through, bloom_source is
    forced to ai_inferred regardless of client input."""
    payload = {
        "candidates": [
            _candidate("A", bloom_level=1),
            _candidate("B", bloom_level=6),
        ],
    }
    resp = client.post("/api/zettels/bulk-from-decomposition", json=payload)
    assert resp.status_code == 200
    body = resp.json()
    rows = list(
        db_session.exec(select(ZettelCard).where(ZettelCard.id.in_(body["created_card_ids"])))
    )
    levels = sorted(c.bloom_level for c in rows)
    assert levels == [1, 6]
    for c in rows:
        assert c.bloom_source == "ai_inferred"


def test_bulk_does_not_create_self_link(client: TestClient, db_session: Session) -> None:
    """Defensive: a candidate that references itself must NOT create a self-link."""
    _ = utcnow_naive()  # exercise import; no-op
    payload = {
        "candidates": [
            _candidate("A", links=[0, 1]),
            _candidate("B"),
        ],
    }
    resp = client.post("/api/zettels/bulk-from-decomposition", json=payload)
    assert resp.status_code == 200
    body = resp.json()
    assert body["link_count"] == 1
    links = list(db_session.exec(select(ZettelLink)))
    for link in links:
        assert link.from_card_id != link.to_card_id
