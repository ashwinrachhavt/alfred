from __future__ import annotations

import logging
from datetime import datetime, timedelta
from unittest.mock import MagicMock

import pytest
from sqlalchemy import create_engine
from sqlmodel import Session, SQLModel

from alfred.models.zettel import ZettelCard, ZettelLink, ZettelReview
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


# ---------------------------------------------------------------------------
# update_link — reverse-row state machine
# ---------------------------------------------------------------------------


def _pair(svc: ZettelkastenService) -> tuple[int, int]:
    a = svc.create_card(title="A")
    b = svc.create_card(title="B")
    return a.id or 0, b.id or 0


def test_update_link_type_only_sync_reverse() -> None:
    session = _session()
    svc = ZettelkastenService(session)
    a, b = _pair(svc)
    links = svc.create_link(from_card_id=a, to_card_id=b, type="supports", bidirectional=True)
    forward = next(link for link in links if link.from_card_id == a)

    updated = svc.update_link(forward.id or 0, type="contradicts")
    assert updated is not None
    assert updated.type == "contradicts"

    rows = session.exec(select(ZettelLink)).all()
    assert len(rows) == 2
    assert {row.type for row in rows} == {"contradicts"}


def test_update_link_type_collision_deletes_existing() -> None:
    session = _session()
    svc = ZettelkastenService(session)
    a, b = _pair(svc)
    supports = svc.create_link(
        from_card_id=a, to_card_id=b, type="supports", bidirectional=False
    )[0]
    related = svc.create_link(
        from_card_id=a, to_card_id=b, type="related", bidirectional=False
    )[0]

    updated = svc.update_link(supports.id or 0, type="related")
    assert updated is not None
    assert updated.type == "related"
    assert updated.id == supports.id

    rows = session.exec(select(ZettelLink)).all()
    assert len(rows) == 1
    assert rows[0].id == supports.id
    assert session.get(ZettelLink, related.id) is None


def test_update_link_bidirectional_false_to_true_creates_reverse() -> None:
    session = _session()
    svc = ZettelkastenService(session)
    a, b = _pair(svc)
    forward = svc.create_link(
        from_card_id=a, to_card_id=b, type="reference", bidirectional=False
    )[0]

    updated = svc.update_link(forward.id or 0, bidirectional=True)
    assert updated is not None
    assert updated.bidirectional is True

    rows = session.exec(select(ZettelLink)).all()
    assert len(rows) == 2
    assert all(row.bidirectional for row in rows)


def test_update_link_bidirectional_true_to_false_deletes_reverse() -> None:
    session = _session()
    svc = ZettelkastenService(session)
    a, b = _pair(svc)
    pair = svc.create_link(from_card_id=a, to_card_id=b, type="related", bidirectional=True)
    forward = next(link for link in pair if link.from_card_id == a)

    updated = svc.update_link(forward.id or 0, bidirectional=False)
    assert updated is not None
    assert updated.bidirectional is False

    rows = session.exec(select(ZettelLink)).all()
    assert len(rows) == 1
    assert rows[0].from_card_id == a and rows[0].to_card_id == b


def test_update_link_drift_missing_reverse_is_tolerated() -> None:
    session = _session()
    svc = ZettelkastenService(session)
    a, b = _pair(svc)
    pair = svc.create_link(from_card_id=a, to_card_id=b, type="related", bidirectional=True)
    forward = next(link for link in pair if link.from_card_id == a)
    reverse = next(link for link in pair if link.from_card_id == b)

    session.delete(reverse)
    session.commit()

    updated = svc.update_link(forward.id or 0, bidirectional=False)
    assert updated is not None
    assert updated.bidirectional is False
    rows = session.exec(select(ZettelLink)).all()
    assert len(rows) == 1


def test_update_link_context_change_syncs_reverse() -> None:
    session = _session()
    svc = ZettelkastenService(session)
    a, b = _pair(svc)
    pair = svc.create_link(from_card_id=a, to_card_id=b, type="related", bidirectional=True)
    forward = next(link for link in pair if link.from_card_id == a)

    updated = svc.update_link(forward.id or 0, context="because X")
    assert updated is not None
    assert updated.context == "because X"
    rows = session.exec(select(ZettelLink)).all()
    assert all(row.context == "because X" for row in rows)


def test_update_link_context_none_clears_on_both_rows() -> None:
    session = _session()
    svc = ZettelkastenService(session)
    a, b = _pair(svc)
    pair = svc.create_link(
        from_card_id=a,
        to_card_id=b,
        type="related",
        context="initial",
        bidirectional=True,
    )
    forward = next(link for link in pair if link.from_card_id == a)

    updated = svc.update_link(forward.id or 0, context=None)
    assert updated is not None
    assert updated.context is None
    rows = session.exec(select(ZettelLink)).all()
    assert all(row.context is None for row in rows)


def test_update_link_context_omitted_is_noop() -> None:
    session = _session()
    svc = ZettelkastenService(session)
    a, b = _pair(svc)
    pair = svc.create_link(
        from_card_id=a,
        to_card_id=b,
        type="related",
        context="keep me",
        bidirectional=True,
    )
    forward = next(link for link in pair if link.from_card_id == a)

    # No context kwarg at all — should leave context untouched.
    updated = svc.update_link(forward.id or 0, type="supports")
    assert updated is not None
    assert updated.context == "keep me"
    rows = session.exec(select(ZettelLink)).all()
    assert all(row.context == "keep me" for row in rows)


def test_update_link_empty_type_raises() -> None:
    session = _session()
    svc = ZettelkastenService(session)
    a, b = _pair(svc)
    forward = svc.create_link(
        from_card_id=a, to_card_id=b, type="related", bidirectional=False
    )[0]

    with pytest.raises(ValueError):
        svc.update_link(forward.id or 0, type="   ")


def test_update_link_not_found_returns_none() -> None:
    session = _session()
    svc = ZettelkastenService(session)
    assert svc.update_link(9999, type="related") is None


# ---------------------------------------------------------------------------
# T2: create_card / create_cards_batch vector sync + session_id kwarg
# ---------------------------------------------------------------------------


def test_create_card_syncs_to_qdrant(monkeypatch: pytest.MonkeyPatch) -> None:
    """create_card must push the new card through ensure_embedding so Qdrant
    sees it immediately (closes crud-vector-sync-gap)."""
    session = _session()
    svc = ZettelkastenService(session)

    mock_ensure = MagicMock(side_effect=lambda card: card)
    monkeypatch.setattr(svc, "ensure_embedding", mock_ensure)

    card = svc.create_card(title="sync me", content="body")

    assert card.id is not None
    mock_ensure.assert_called_once()
    # Called with the freshly-saved card.
    called_with = mock_ensure.call_args.args[0]
    assert isinstance(called_with, ZettelCard)
    assert called_with.id == card.id


def test_create_cards_batch_syncs_all_to_qdrant(monkeypatch: pytest.MonkeyPatch) -> None:
    """Each card in a batch must be pushed to Qdrant individually."""
    session = _session()
    svc = ZettelkastenService(session)

    mock_ensure = MagicMock(side_effect=lambda card: card)
    monkeypatch.setattr(svc, "ensure_embedding", mock_ensure)

    cards = svc.create_cards_batch(
        [{"title": "A"}, {"title": "B"}, {"title": "C"}]
    )

    assert len(cards) == 3
    assert mock_ensure.call_count == 3
    synced_ids = {call.args[0].id for call in mock_ensure.call_args_list}
    assert synced_ids == {c.id for c in cards}


def test_create_card_accepts_session_id_kwarg(monkeypatch: pytest.MonkeyPatch) -> None:
    """session_id kwarg must be plumbed through to the ZettelCard row.

    We don't need a real zettel_sessions row — the FK is only enforced
    at the DB level, and sqlite doesn't enforce by default. This exercises
    the kwarg wiring.
    """
    session = _session()
    svc = ZettelkastenService(session)

    monkeypatch.setattr(svc, "ensure_embedding", MagicMock(side_effect=lambda card: card))

    card = svc.create_card(title="scoped", session_id=42)

    assert card.session_id == 42


def test_create_card_survives_ensure_embedding_failure(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """If ensure_embedding raises (e.g. Qdrant/OpenAI down), create_card
    must still return a saved card and log a warning — the card in
    Postgres is higher-priority than the embedding backfill."""
    session = _session()
    svc = ZettelkastenService(session)

    def boom(_card: ZettelCard) -> ZettelCard:
        raise RuntimeError("qdrant offline")

    monkeypatch.setattr(svc, "ensure_embedding", boom)

    with caplog.at_level(logging.WARNING, logger="alfred.services.zettelkasten_service"):
        card = svc.create_card(title="resilient", content="body")

    # Card is saved in Postgres despite the sync failure.
    assert isinstance(card, ZettelCard)
    assert card.id is not None
    persisted = session.get(ZettelCard, card.id)
    assert persisted is not None
    assert persisted.title == "resilient"

    # Warning logged with card id + error message.
    warnings = [rec for rec in caplog.records if rec.levelno == logging.WARNING]
    assert any(
        "ensure_embedding failed" in rec.getMessage() and "qdrant offline" in rec.getMessage()
        for rec in warnings
    )
