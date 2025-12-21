from __future__ import annotations

from datetime import datetime, timedelta

from alfred.models.zettel import ZettelReview
from alfred.services.zettelkasten_service import ZettelkastenService
from sqlalchemy import create_engine
from sqlmodel import Session, SQLModel, select


def _session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    return Session(engine)


def test_card_creation_and_listing() -> None:
    session = _session()
    svc = ZettelkastenService(session)
    card = svc.create_card(title="Z1", tags=["a", "b"], topic="ai")
    assert card.id is not None

    items = svc.list_cards(topic="ai")
    assert len(items) == 1
    assert items[0].title == "Z1"
    tagged = svc.list_cards(tag="a")
    assert tagged and tagged[0].id == card.id


def test_bidirectional_links() -> None:
    session = _session()
    svc = ZettelkastenService(session)
    a = svc.create_card(title="A")
    b = svc.create_card(title="B")

    links = svc.create_link(from_card_id=a.id or 0, to_card_id=b.id or 0, bidirectional=True)
    assert len(links) == 2

    related = svc.list_links(card_id=a.id or 0)
    assert len(related) == 2  # includes both directions


def test_review_progression() -> None:
    session = _session()
    svc = ZettelkastenService(session)
    card = svc.create_card(title="Memory Palace")

    open_review = session.exec(
        select(ZettelReview)
        .where(ZettelReview.card_id == card.id)
        .where(ZettelReview.completed_at.is_(None))
    ).first()
    assert open_review is not None
    assert open_review.stage == 1

    # Mark due and complete with a passing score
    open_review.due_at = datetime.utcnow() - timedelta(minutes=5)
    session.add(open_review)
    session.commit()

    completed = svc.complete_review(review=open_review, score=0.9)
    assert completed.completed_at is not None

    next_review = session.exec(
        select(ZettelReview)
        .where(ZettelReview.card_id == card.id)
        .where(ZettelReview.completed_at.is_(None))
        .order_by(ZettelReview.due_at.asc())
    ).first()
    assert next_review is not None
    assert next_review.stage == 2
