"""Integration tests for ``/api/chat/omnibox``."""

from __future__ import annotations

from collections.abc import Generator
from datetime import UTC, date, datetime

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel

from alfred.api.chat.routes import router as chat_router
from alfred.api.dependencies import get_db_session
from alfred.models.doc_storage import DocumentRow
from alfred.models.zettel import ZettelCard


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
def client(session: Session) -> TestClient:
    app = FastAPI()
    app.include_router(chat_router)
    app.dependency_overrides[get_db_session] = lambda: session
    return TestClient(app)


def _card(session: Session, **overrides) -> ZettelCard:
    data = {
        "title": "Default card",
        "content": "default content",
        "summary": "default summary",
        "topic": "default",
        "tags": [],
        "created_at": datetime(2026, 5, 1, 10, 0, tzinfo=UTC),
        "updated_at": datetime(2026, 5, 1, 10, 0, tzinfo=UTC),
    }
    data.update(overrides)
    card = ZettelCard(**data)
    session.add(card)
    session.commit()
    session.refresh(card)
    return card


def _document(session: Session, **overrides) -> DocumentRow:
    data = {
        "source_url": "https://example.com/default",
        "title": "Default document",
        "cleaned_text": "default body",
        "hash": f"hash-{datetime.now(tz=UTC).timestamp()}",
        "day_bucket": date(2026, 5, 1),
        "captured_at": datetime(2026, 5, 1, 9, 0, tzinfo=UTC),
        "created_at": datetime(2026, 5, 1, 9, 0, tzinfo=UTC),
        "updated_at": datetime(2026, 5, 1, 9, 0, tzinfo=UTC),
    }
    data.update(overrides)
    doc = DocumentRow(**data)
    session.add(doc)
    session.commit()
    session.refresh(doc)
    return doc


def test_omnibox_matches_zettel_title_topic_tags_summary_and_content(
    client: TestClient, session: Session
) -> None:
    title = _card(session, title="Memory palace techniques")
    topic = _card(session, title="Topic match", topic="Memory")
    tag = _card(session, title="Tag match", tags=["memory"])
    summary = _card(session, title="Summary match", summary="A note about memory")
    content = _card(session, title="Content match", content="Practice memory every day")
    _card(session, title="Unrelated", topic="unrelated", tags=["focus"])

    resp = client.get("/api/chat/omnibox", params={"q": "memory"})

    assert resp.status_code == 200, resp.text
    body = resp.json()
    zettel_ids = [item["id"] for item in body["results"] if item["kind"] == "zettel"]
    assert zettel_ids[:5] == [title.id, topic.id, tag.id, summary.id, content.id]


def test_omnibox_returns_document_matches_and_action_rows(
    client: TestClient, session: Session
) -> None:
    doc = _document(
        session,
        title="Learning notes",
        cleaned_text="This article discusses memory consolidation.",
        topics={"primary": "Learning"},
    )

    resp = client.get("/api/chat/omnibox", params={"q": "memory"})

    assert resp.status_code == 200, resp.text
    body = resp.json()
    document = next(item for item in body["results"] if item["kind"] == "document")
    assert document["id"] == str(doc.id)
    assert document["title"] == "Learning notes"
    assert document["topic"] == "Learning"
    actions = {item["action"]: item for item in body["results"] if item["kind"] == "action"}
    assert set(actions) == {"search_all", "create_card"}
    assert actions["search_all"]["title"] == "Search all knowledge for memory"
    assert actions["create_card"]["title"] == "Create a card from memory"
    assert "Polymath" in actions["search_all"]["description"]
    assert "Polymath" in actions["create_card"]["description"]


def test_omnibox_bare_query_returns_recent_sources_and_default_actions(
    client: TestClient, session: Session
) -> None:
    card = _card(
        session,
        title="Recent card",
        updated_at=datetime(2026, 5, 2, 12, 0, tzinfo=UTC),
    )
    doc = _document(
        session,
        title="Recent document",
        captured_at=datetime(2026, 5, 2, 11, 0, tzinfo=UTC),
    )

    resp = client.get("/api/chat/omnibox")

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["results"][0]["kind"] == "zettel"
    assert body["results"][0]["id"] == card.id
    assert any(item["kind"] == "document" and item["id"] == str(doc.id) for item in body["results"])
    assert {item["action"] for item in body["results"] if item["kind"] == "action"} == {
        "search_all",
        "create_card",
    }


def test_omnibox_limit_one_returns_exact_zettel_before_action(
    client: TestClient, session: Session
) -> None:
    card = _card(session, title="memory")

    resp = client.get("/api/chat/omnibox", params={"q": "memory", "limit": "1"})

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert len(body["results"]) == 1
    assert body["results"][0]["kind"] == "zettel"
    assert body["results"][0]["id"] == card.id


def test_omnibox_bounded_candidates_keep_old_exact_title_match(
    client: TestClient, session: Session
) -> None:
    exact = _card(
        session,
        title="memory",
        updated_at=datetime(2026, 5, 1, 8, 0, tzinfo=UTC),
    )
    for index in range(25):
        _card(
            session,
            title=f"Recent content match {index}",
            content="A recent note mentioning memory in the body.",
            updated_at=datetime(2026, 5, 2, 8, index, tzinfo=UTC),
        )

    resp = client.get("/api/chat/omnibox", params={"q": "memory", "limit": "1"})

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["results"][0]["kind"] == "zettel"
    assert body["results"][0]["id"] == exact.id


def test_omnibox_excludes_archived_zettels(client: TestClient, session: Session) -> None:
    active = _card(session, title="Memory systems")
    _card(session, title="Memory archive", status="archived")

    resp = client.get("/api/chat/omnibox", params={"q": "memory"})

    assert resp.status_code == 200, resp.text
    zettel_ids = [item["id"] for item in resp.json()["results"] if item["kind"] == "zettel"]
    assert zettel_ids == [active.id]


def test_omnibox_excerpt_uses_matching_zettel_field(
    client: TestClient, session: Session
) -> None:
    _card(
        session,
        title="Practice note",
        summary="This summary does not include the query.",
        content="Daily memory drills strengthen recall.",
    )

    resp = client.get("/api/chat/omnibox", params={"q": "memory"})

    assert resp.status_code == 200, resp.text
    zettel = next(item for item in resp.json()["results"] if item["kind"] == "zettel")
    assert "memory drills" in zettel["excerpt"]
