from __future__ import annotations

from collections.abc import Generator

import pytest
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, select

from alfred.models.zettel import ZettelCard, ZettelLink, ZettelSession
from alfred.schemas.zettel import BulkFromDecompositionRequest
from alfred.services.session_service import SessionService
from alfred.services.zettel_decomposition_commit import (
    ZettelDecompositionCommitError,
    ZettelDecompositionCommitService,
)
from alfred.services.zettelkasten_service import ZettelkastenService


@pytest.fixture()
def session() -> Generator[Session, None, None]:
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as db:
        yield db


@pytest.fixture(autouse=True)
def _stub_embeddings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ZettelkastenService, "ensure_embedding", lambda _self, card: card)


def _request(*, session_id: int | None = None) -> BulkFromDecompositionRequest:
    return BulkFromDecompositionRequest.model_validate(
        {
            "session_id": session_id,
            "shared_topic": "systems",
            "source_url": "https://example.com/source",
            "candidates": [
                {
                    "title": "A",
                    "content": "A content",
                    "bloom_level": 2,
                    "tags": ["one"],
                    "links_to_siblings": [1, 1, 99, -1, 0],
                },
                {
                    "title": "B",
                    "content": "B content",
                    "bloom_level": 4,
                    "tags": ["two"],
                    "links_to_siblings": [],
                },
            ],
        }
    )


def test_commit_creates_cards_and_valid_sibling_links(session: Session) -> None:
    result = ZettelDecompositionCommitService(session).commit(_request())

    assert len(result.created_card_ids) == 2
    assert result.link_count == 1

    cards = session.exec(
        select(ZettelCard).where(ZettelCard.id.in_(result.created_card_ids))
    ).all()
    by_title = {card.title: card for card in cards}
    assert by_title["A"].topic == "systems"
    assert by_title["A"].source_url == "https://example.com/source"
    assert by_title["A"].bloom_source == "ai_inferred"
    assert by_title["A"].bloom_level == 2
    assert by_title["B"].bloom_level == 4

    links = session.exec(select(ZettelLink)).all()
    pairs = {(link.from_card_id, link.to_card_id) for link in links}
    assert pairs == {
        (result.created_card_ids[0], result.created_card_ids[1]),
        (result.created_card_ids[1], result.created_card_ids[0]),
    }


def test_commit_rejects_ended_session(session: Session) -> None:
    row = ZettelSession(title="ended")
    session.add(row)
    session.commit()
    session.refresh(row)
    assert row.id is not None
    SessionService(session).end(row.id)

    with pytest.raises(ZettelDecompositionCommitError, match="already ended"):
        ZettelDecompositionCommitService(session).commit(_request(session_id=row.id))
