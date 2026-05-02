"""Tests for SessionService (T6)."""

from __future__ import annotations

from datetime import datetime, timedelta
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine
from sqlmodel import Session, SQLModel

from alfred.models.zettel import ZettelCard, ZettelLink, ZettelSession
from alfred.schemas.zettel import ZettelSessionCreateRequest
from alfred.services.session_service import (
    SessionAlreadyEnded,
    SessionNotFound,
    SessionService,
)
from alfred.services.zettelkasten_service import ZettelkastenService

try:
    from sqlmodel import select  # type: ignore
except Exception:  # pragma: no cover

    def select(*_args, **_kwargs):  # type: ignore
        raise ImportError("sqlmodel.select not available in test environment")


def _session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    return Session(engine)


class _FakeLLMResponse:
    def __init__(self, text: str) -> None:
        self.content = text


class _FakeLLM:
    def __init__(self, text: str) -> None:
        self.text = text
        self.calls: list[list[dict]] = []

    def invoke(self, messages):
        self.calls.append(messages)
        return _FakeLLMResponse(self.text)


# ---------------------------------------------------------------------------
# create / status derivation
# ---------------------------------------------------------------------------


def test_create_session_persists_fields() -> None:
    session = _session()
    svc = SessionService(session)
    row = svc.create(
        ZettelSessionCreateRequest(
            title="X",
            shared_topic="Y",
            shared_tags=["a", "b"],
            source_context="ctx",
        )
    )
    assert row.id is not None
    assert row.title == "X"
    assert row.shared_topic == "Y"
    assert row.shared_tags == ["a", "b"]
    assert row.source_context == "ctx"
    assert row.ended_at is None
    assert row.card_count == 0
    assert row.status == "active"


def test_session_status_derivation_active() -> None:
    session = _session()
    svc = SessionService(session)
    row = svc.create(ZettelSessionCreateRequest(title="fresh"))
    assert row.status == "active"


def test_session_status_derivation_ended() -> None:
    session = _session()
    row = ZettelSession(
        title="done",
        ended_at=datetime.utcnow(),
        summary_card_id=42,
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    assert row.status == "ended"


def test_session_status_derivation_abandoned() -> None:
    session = _session()
    row = ZettelSession(
        title="abandoned",
        ended_at=datetime.utcnow(),
        summary_card_id=None,
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    assert row.status == "abandoned"


# ---------------------------------------------------------------------------
# end()
# ---------------------------------------------------------------------------


def test_end_empty_session_marks_abandoned_no_summary() -> None:
    session = _session()
    svc = SessionService(session)
    row = svc.create(ZettelSessionCreateRequest(title="empty"))

    ended = svc.end(row.id)

    assert ended.ended_at is not None
    assert ended.summary_card_id is None
    assert ended.summary is None
    assert ended.status == "abandoned"


def test_end_session_with_cards_creates_summary_card() -> None:
    session = _session()
    zsvc = ZettelkastenService(session)
    svc = SessionService(session)

    sess = svc.create(ZettelSessionCreateRequest(title="Sitting", shared_topic="epistemology"))
    c1 = zsvc.create_card(title="Card 1", summary="First idea", session_id=sess.id)
    c2 = zsvc.create_card(title="Card 2", summary="Second idea", session_id=sess.id)

    fake = _FakeLLM("This sitting argues that knowledge builds on itself.")

    with patch(
        "alfred.services.session_service.get_chat_model",
        lambda **_: fake,
    ):
        ended = svc.end(sess.id)

    assert fake.calls, "LLM should be invoked when cards exist"
    assert ended.ended_at is not None
    assert ended.summary_card_id is not None
    assert ended.summary == "This sitting argues that knowledge builds on itself."
    assert ended.status == "ended"

    summary_card = session.get(ZettelCard, ended.summary_card_id)
    assert summary_card is not None
    assert summary_card.bloom_level == 6
    assert summary_card.bloom_source == "ai_inferred"
    assert "session-summary" in (summary_card.tags or [])

    links = list(session.exec(select(ZettelLink).where(ZettelLink.type == "session_summary")))
    pairs = {(link.from_card_id, link.to_card_id) for link in links}
    assert (summary_card.id, c1.id) in pairs
    assert (c1.id, summary_card.id) in pairs
    assert (summary_card.id, c2.id) in pairs
    assert (c2.id, summary_card.id) in pairs


def test_end_session_falls_back_deterministic_on_llm_error() -> None:
    session = _session()
    zsvc = ZettelkastenService(session)
    svc = SessionService(session)

    sess = svc.create(ZettelSessionCreateRequest(title="Sitting", shared_topic="systems"))
    zsvc.create_card(title="Entropy basics", summary="State decays.", session_id=sess.id)

    class _Boom:
        def invoke(self, _messages):
            raise RuntimeError("LLM offline")

    with patch(
        "alfred.services.session_service.get_chat_model",
        lambda **_: _Boom(),
    ):
        ended = svc.end(sess.id)

    assert ended.summary is not None
    assert "Entropy basics" in ended.summary
    assert "systems" in ended.summary
    assert ended.summary_card_id is not None
    assert ended.status == "ended"


def test_end_session_twice_raises_already_ended() -> None:
    session = _session()
    svc = SessionService(session)
    sess = svc.create(ZettelSessionCreateRequest(title="once"))

    svc.end(sess.id)
    with pytest.raises(SessionAlreadyEnded):
        svc.end(sess.id)


# ---------------------------------------------------------------------------
# hydrate()
# ---------------------------------------------------------------------------


def test_hydrate_returns_top_3_full_and_older_as_stubs() -> None:
    session = _session()
    zsvc = ZettelkastenService(session)
    svc = SessionService(session)

    sess = svc.create(ZettelSessionCreateRequest(title="hydration"))
    cards = []
    for i in range(5):
        c = zsvc.create_card(
            title=f"Card {i}",
            summary=f"Summary {i}",
            session_id=sess.id,
        )
        cards.append(c)

    base = datetime.utcnow() - timedelta(days=10)
    for i, c in enumerate(cards):
        c.updated_at = base + timedelta(hours=i)
        session.add(c)
    session.commit()

    resp = svc.hydrate(sess.id)

    assert len(resp.full_cards) == 3
    full_ids = [c.id for c in resp.full_cards]
    assert full_ids == [cards[4].id, cards[3].id, cards[2].id]

    assert len(resp.stub_cards) == 2
    stub_ids = [s.id for s in resp.stub_cards]
    assert stub_ids == [cards[1].id, cards[0].id]
    assert all(s.is_archived is False for s in resp.stub_cards)
    assert all(isinstance(s.bloom_level, int) for s in resp.stub_cards)


def test_hydrate_includes_archived_in_stubs() -> None:
    session = _session()
    zsvc = ZettelkastenService(session)
    svc = SessionService(session)

    sess = svc.create(ZettelSessionCreateRequest(title="mixed"))
    active = zsvc.create_card(title="Active card", session_id=sess.id)
    archived = zsvc.create_card(title="Old card", session_id=sess.id)
    zsvc.archive_card(archived)

    active.updated_at = datetime.utcnow()
    session.add(active)
    session.commit()

    resp = svc.hydrate(sess.id)

    full_titles = {c.title for c in resp.full_cards}
    assert "Active card" in full_titles
    stub_ids = {s.id for s in resp.stub_cards}
    assert archived.id in stub_ids
    archived_stub = next(s for s in resp.stub_cards if s.id == archived.id)
    assert archived_stub.is_archived is True


def test_hydrate_raises_on_missing_session() -> None:
    session = _session()
    svc = SessionService(session)
    with pytest.raises(SessionNotFound):
        svc.hydrate(9999)


# ---------------------------------------------------------------------------
# touch()
# ---------------------------------------------------------------------------


def test_session_service_touch_bumps_updated_at() -> None:
    """touch() must advance updated_at so the T8 beat sees activity."""
    session = _session()
    svc = SessionService(session)
    row = svc.create(ZettelSessionCreateRequest(title="active"))
    assert row.id is not None
    original_updated = row.updated_at
    assert original_updated is not None

    # Backdate updated_at so the bump is unambiguously detectable even
    # on systems where monotonic resolution is coarse.
    row.updated_at = original_updated - timedelta(minutes=5)
    session.add(row)
    session.commit()
    backdated = row.updated_at

    svc.touch(row.id)
    session.expire_all()
    refetched = session.get(ZettelSession, row.id)
    assert refetched is not None
    assert refetched.updated_at is not None
    assert refetched.updated_at > backdated


def test_session_service_touch_missing_session_is_noop() -> None:
    """touch() on a non-existent session must not raise."""
    session = _session()
    svc = SessionService(session)
    # No row exists with id 9999 -- should silently do nothing.
    svc.touch(9999)
