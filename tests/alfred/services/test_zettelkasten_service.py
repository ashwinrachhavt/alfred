from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import create_engine
from sqlmodel import Session, SQLModel

from alfred.models.zettel import ZettelReview
from alfred.services.zettelkasten_service import ZettelkastenService

try:  # avoid ImportError when sqlmodel.select is unavailable in minimal envs
    from sqlmodel import select  # type: ignore
except Exception:  # pragma: no cover - fallback for stripped sqlmodel

    def select(*_args, **_kwargs):  # type: ignore
        raise ImportError("sqlmodel.select not available in test environment")


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

    # Tag filtering uses PostgreSQL jsonb @> operator, skip on SQLite
    dialect = session.bind.dialect.name if session.bind else "unknown"
    if dialect == "postgresql":
        tagged = svc.list_cards(tags=["a"])
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


def test_extended_graph_summary_basic() -> None:
    """extended_graph_summary returns nodes, edges, clusters, gaps, meta."""
    session = _session()
    svc = ZettelkastenService(session)
    a = svc.create_card(title="Alpha", topic="ai", tags=["ml"], importance=3)
    b = svc.create_card(title="Beta", topic="ai", tags=["nlp"], importance=5)
    svc.create_link(from_card_id=a.id or 0, to_card_id=b.id or 0, bidirectional=False)

    result = svc.extended_graph_summary(include_clusters=False, include_gaps=False)

    # Structure assertions
    assert "nodes" in result
    assert "edges" in result
    assert "clusters" in result
    assert "gaps" in result
    assert "meta" in result

    # Nodes carry all expected fields
    assert len(result["nodes"]) == 2
    node_a = next(n for n in result["nodes"] if n["id"] == a.id)
    assert node_a["title"] == "Alpha"
    assert node_a["topic"] == "ai"
    assert node_a["tags"] == ["ml"]
    assert node_a["importance"] == 3
    assert node_a["status"] == "active"
    assert node_a["degree"] == 1
    assert node_a["created_at"] is not None

    # Edges use source/target keys (react-force-graph compatible)
    assert len(result["edges"]) == 1
    edge = result["edges"][0]
    assert edge["source"] == a.id
    assert edge["target"] == b.id
    assert edge["type"] == "reference"

    # Meta is populated
    meta = result["meta"]
    assert meta["total_cards"] == 2
    assert meta["total_edges"] == 1
    assert meta["cluster_count"] == 0
    assert isinstance(meta["embedding_coverage_pct"], float)


def test_extended_graph_summary_due_at() -> None:
    """Open reviews populate due_at on nodes."""
    session = _session()
    svc = ZettelkastenService(session)
    card = svc.create_card(title="Review me")

    # create_card automatically creates a stage-1 review -- find it
    open_review = session.exec(
        select(ZettelReview)
        .where(ZettelReview.card_id == card.id)
        .where(ZettelReview.completed_at.is_(None))
    ).first()
    assert open_review is not None

    result = svc.extended_graph_summary()
    node = next(n for n in result["nodes"] if n["id"] == card.id)
    assert node["due_at"] is not None


def test_extended_graph_summary_gaps() -> None:
    """Stub cards with inbound links appear in gaps when include_gaps=True."""
    session = _session()
    svc = ZettelkastenService(session)
    active = svc.create_card(title="Active card")
    stub = svc.create_card(title="Stub card")

    # Manually set status to 'stub'
    stub.status = "stub"
    session.add(stub)
    session.commit()
    session.refresh(stub)

    svc.create_link(from_card_id=active.id or 0, to_card_id=stub.id or 0, bidirectional=False)

    result = svc.extended_graph_summary(include_gaps=True)
    assert len(result["gaps"]) == 1
    gap = result["gaps"][0]
    assert gap["id"] == stub.id
    assert gap["title"] == "Stub card"
    assert gap["inbound_link_count"] == 1
