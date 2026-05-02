"""Tests for the abandon_stale_sessions Celery beat task (T8)."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel

from alfred.core.utils import utcnow_naive
from alfred.models.zettel import (  # noqa: F401 - ensure tables exist
    ZettelCard,
    ZettelLink,
    ZettelReview,
    ZettelSession,
)


@pytest.fixture()
def db_session(monkeypatch):
    """Provide an in-memory SQLite DB and patch SessionLocal to return it.

    StaticPool + check_same_thread=False lets multiple calls share the
    single in-memory database, matching how the task would use a real DB.
    """
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    session = Session(engine)

    # Patch SessionLocal inside alfred.core.database so the task picks up
    # this in-memory session instead of the real Postgres one.
    import alfred.core.database as db_mod

    def _factory():
        # Return a new Session over the same engine on each call; the
        # task calls SessionLocal() once per invocation and closes it.
        return Session(engine)

    monkeypatch.setattr(db_mod, "SessionLocal", _factory)

    yield session
    session.close()


def _make_session(
    db: Session,
    *,
    updated_hours_ago: float = 0.0,
    ended_at: datetime | None = None,
    summary_card_id: int | None = None,
    title: str | None = None,
) -> ZettelSession:
    now = utcnow_naive()
    past = now - timedelta(hours=updated_hours_ago)
    row = ZettelSession(
        title=title,
        created_at=past,
        updated_at=past,
        ended_at=ended_at,
        summary_card_id=summary_card_id,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


# ---------------------------------------------------------------------------
# task behavior
# ---------------------------------------------------------------------------


def test_abandon_stale_sessions_marks_sessions_over_24h_idle(db_session):
    """Two sessions idle 25h and 26h should flip abandoned, the 5h one should not."""
    from alfred.tasks.session_cleanup import abandon_stale_sessions

    stale_25h = _make_session(db_session, updated_hours_ago=25, title="stale 25")
    stale_26h = _make_session(db_session, updated_hours_ago=26, title="stale 26")
    fresh_5h = _make_session(db_session, updated_hours_ago=5, title="fresh")

    result = abandon_stale_sessions()
    assert result == {"abandoned_count": 2}

    db_session.expire_all()

    s25 = db_session.get(ZettelSession, stale_25h.id)
    s26 = db_session.get(ZettelSession, stale_26h.id)
    s5 = db_session.get(ZettelSession, fresh_5h.id)

    assert s25.ended_at is not None
    assert s26.ended_at is not None
    assert s5.ended_at is None

    # Status property should derive as "abandoned" (summary_card_id is NULL).
    assert s25.status == "abandoned"
    assert s26.status == "abandoned"
    assert s5.status == "active"


def test_abandon_stale_sessions_preserves_cards(db_session):
    """Cards in an abandoned session remain intact (same session_id, same status)."""
    from alfred.tasks.session_cleanup import abandon_stale_sessions

    stale = _make_session(db_session, updated_hours_ago=25, title="stale with cards")
    card_a = ZettelCard(title="Card A", session_id=stale.id, status="active")
    card_b = ZettelCard(title="Card B", session_id=stale.id, status="active")
    db_session.add_all([card_a, card_b])
    db_session.commit()
    db_session.refresh(card_a)
    db_session.refresh(card_b)
    a_id, b_id = card_a.id, card_b.id

    abandon_stale_sessions()
    db_session.expire_all()

    s = db_session.get(ZettelSession, stale.id)
    assert s.ended_at is not None
    assert s.status == "abandoned"

    a = db_session.get(ZettelCard, a_id)
    b = db_session.get(ZettelCard, b_id)
    assert a is not None and b is not None
    assert a.session_id == stale.id
    assert b.session_id == stale.id
    assert a.status == "active"
    assert b.status == "active"


def test_abandon_stale_sessions_leaves_summary_card_id_null(db_session):
    """Abandoned sessions must NOT gain a summary_card_id (that's the ended vs abandoned signal)."""
    from alfred.tasks.session_cleanup import abandon_stale_sessions

    stale = _make_session(db_session, updated_hours_ago=30, title="stale empty")
    # Add a card so there would be something to summarize, to prove the
    # task doesn't run the summary branch.
    db_session.add(ZettelCard(title="Unsummarized", session_id=stale.id, status="active"))
    db_session.commit()

    abandon_stale_sessions()
    db_session.expire_all()

    s = db_session.get(ZettelSession, stale.id)
    assert s.ended_at is not None
    assert s.summary_card_id is None
    assert s.summary is None
    assert s.status == "abandoned"


def test_abandon_stale_sessions_skips_already_ended(db_session):
    """A session already ended 48h ago must not have its ended_at rewritten."""
    from alfred.tasks.session_cleanup import abandon_stale_sessions

    original_ended_at = utcnow_naive() - timedelta(hours=48)
    ended = ZettelSession(
        title="already ended",
        created_at=original_ended_at,
        updated_at=original_ended_at,
        ended_at=original_ended_at,
    )
    db_session.add(ended)
    db_session.commit()
    db_session.refresh(ended)

    result = abandon_stale_sessions()
    assert result == {"abandoned_count": 0}

    db_session.expire_all()
    s = db_session.get(ZettelSession, ended.id)
    # Compare at microsecond precision; the row should be byte-for-byte unchanged.
    assert s.ended_at == original_ended_at


def test_abandon_stale_sessions_returns_count(db_session):
    """2 stale + 2 fresh should return abandoned_count=2."""
    from alfred.tasks.session_cleanup import abandon_stale_sessions

    _make_session(db_session, updated_hours_ago=25)
    _make_session(db_session, updated_hours_ago=50)
    _make_session(db_session, updated_hours_ago=1)
    _make_session(db_session, updated_hours_ago=0)

    result = abandon_stale_sessions()
    assert result == {"abandoned_count": 2}


def test_abandon_stale_sessions_empty_db_returns_zero(db_session):
    """No sessions at all -- task is a no-op and returns zero."""
    from alfred.tasks.session_cleanup import abandon_stale_sessions

    result = abandon_stale_sessions()
    assert result == {"abandoned_count": 0}
