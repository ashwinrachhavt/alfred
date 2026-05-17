from __future__ import annotations

from collections.abc import Generator

import pytest
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, select

from alfred.models.zettel import WikiLink, ZettelCard
from alfred.services.zettel_links import ZettelLinkService
from alfred.services.zettel_wiki_links import ZettelWikiLinkService


@pytest.fixture()
def session() -> Generator[Session, None, None]:
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def _card(session: Session, title: str) -> ZettelCard:
    card = ZettelCard(title=title, content="", tags=[])
    session.add(card)
    session.commit()
    session.refresh(card)
    return card


def test_sync_wiki_links_replaces_source_targets(session: Session) -> None:
    service = ZettelWikiLinkService(session)
    first = _card(session, "First")
    second = _card(session, "Second")
    third = _card(session, "Third")

    service.sync_wiki_links(
        source_type="zettel",
        source_id="source-1",
        target_card_ids=[first.id or 0, second.id or 0],
    )
    service.sync_wiki_links(
        source_type="zettel",
        source_id="source-1",
        target_card_ids=[second.id or 0, third.id or 0],
    )

    rows = session.exec(select(WikiLink).where(WikiLink.source_id == "source-1")).all()
    assert {row.target_card_id for row in rows} == {second.id, third.id}


def test_list_backlinks_merges_wiki_links_and_graph_links(session: Session) -> None:
    wiki_service = ZettelWikiLinkService(session)
    source = _card(session, "Source")
    target = _card(session, "Target")
    graph_source = _card(session, "Graph source")

    wiki_service.sync_wiki_links(
        source_type="zettel",
        source_id=str(source.id),
        target_card_ids=[target.id or 0],
    )
    ZettelLinkService(session).create_link(
        from_card_id=graph_source.id or 0,
        to_card_id=target.id or 0,
        bidirectional=False,
    )

    backlinks = wiki_service.list_backlinks(target.id or 0)

    assert {
        (backlink["source_type"], backlink["source_id"], backlink["source_title"])
        for backlink in backlinks
    } == {
        ("zettel", str(source.id), "Source"),
        ("zettel", str(graph_source.id), "Graph source"),
    }
