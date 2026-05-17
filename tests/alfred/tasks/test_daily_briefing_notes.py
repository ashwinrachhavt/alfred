"""Behavior tests for build_daily_briefing's notes_touched_today extension.

Pinned shape lives in tests/alfred/api/today/test_contract.py. These tests
exercise the data path: notes updated within today's window appear; archived
notes do not; notes outside the window do not.
"""
from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlmodel import Session, SQLModel

from alfred.models.notes import NoteRow, WorkspaceRow
from alfred.tasks import daily_briefing as db_mod


@pytest.fixture()
def engine_with_data():
    """In-memory SQLite engine with one workspace + 4 notes spanning windows."""
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)

    today = date(2026, 5, 15)
    today_noon_utc = datetime(2026, 5, 15, 12, 0, tzinfo=UTC)
    yesterday_utc = datetime(2026, 5, 14, 12, 0, tzinfo=UTC)

    with Session(engine) as session:
        ws = WorkspaceRow(name="Personal", icon="📓", user_id=None)
        session.add(ws)
        session.commit()
        session.refresh(ws)

        # Note 1: updated today, active — should appear
        n1 = NoteRow(
            title="Today's note",
            workspace_id=ws.id,
            content_markdown="hello",
            created_at=today_noon_utc,
            updated_at=today_noon_utc,
        )
        # Note 2: updated yesterday — should NOT appear
        n2 = NoteRow(
            title="Yesterday's note",
            workspace_id=ws.id,
            content_markdown="hi",
            created_at=yesterday_utc,
            updated_at=yesterday_utc,
        )
        # Note 3: updated today but archived — should NOT appear
        n3 = NoteRow(
            title="Archived today",
            workspace_id=ws.id,
            content_markdown="x",
            created_at=today_noon_utc,
            updated_at=today_noon_utc,
            is_archived=True,
        )
        # Note 4: updated today, active — should appear
        n4 = NoteRow(
            title="Another today's note",
            workspace_id=ws.id,
            content_markdown="y",
            created_at=today_noon_utc,
            updated_at=today_noon_utc + timedelta(hours=1),
        )
        session.add_all([n1, n2, n3, n4])
        session.commit()

    return engine, today


def test_build_daily_briefing_includes_notes_touched_today(
    engine_with_data, monkeypatch: pytest.MonkeyPatch
) -> None:
    engine, today = engine_with_data

    # Re-bind SessionLocal to the test engine
    def _session_local():
        return Session(engine)

    monkeypatch.setattr(db_mod, "SessionLocal", _session_local)

    briefing = db_mod.build_daily_briefing(target_date=today, tz_name="UTC")

    titles = {n.title for n in briefing.notes}
    assert titles == {"Today's note", "Another today's note"}
    assert briefing.stats.total_notes_touched == 2


def test_build_daily_briefing_empty_notes_when_none_touched(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)

    def _session_local():
        return Session(engine)

    monkeypatch.setattr(db_mod, "SessionLocal", _session_local)

    briefing = db_mod.build_daily_briefing(target_date=date(2026, 5, 15), tz_name="UTC")

    assert briefing.notes == []
    assert briefing.stats.total_notes_touched == 0


def test_build_daily_briefing_notes_in_total_events(
    engine_with_data, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Regression: total_events must include the notes count.
    Without this, the calendar / summary widgets undercount user activity.
    """
    engine, today = engine_with_data

    def _session_local():
        return Session(engine)

    monkeypatch.setattr(db_mod, "SessionLocal", _session_local)

    briefing = db_mod.build_daily_briefing(target_date=today, tz_name="UTC")

    expected = (
        len(briefing.captures)
        + len(briefing.stored_cards)
        + len(briefing.connections)
        + len(briefing.reviews)
        + len(briefing.gaps)
        + len(briefing.notes)
    )
    assert briefing.stats.total_events == expected
    assert briefing.stats.total_events >= 2  # at least the 2 notes
