"""Tests for ZettelCreationStream orchestrator."""

from __future__ import annotations

import json
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel

from alfred.models.zettel import ZettelCard, ZettelReview  # noqa: F401 — ensure tables exist
from alfred.schemas.zettel import ZettelCardCreate
from alfred.services.zettel_creation_stream import ZettelCreationStream, _sse


def _parse_sse_events(raw_events: list[str]) -> list[tuple[str, dict]]:
    """Parse SSE strings into (event_name, data) tuples."""
    results = []
    for raw in raw_events:
        lines = raw.strip().split("\n")
        event_name = ""
        data = {}
        for line in lines:
            if line.startswith("event: "):
                event_name = line[7:]
            elif line.startswith("data: "):
                data = json.loads(line[6:])
        if event_name:
            results.append((event_name, data))
    return results


@pytest.fixture()
def db_session() -> Session:
    # StaticPool reuses a single connection for all threads, which lets
    # asyncio.to_thread access the same in-memory SQLite database.
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


@pytest.mark.asyncio
@patch(
    "alfred.services.zettelkasten_service.ZettelkastenService._try_sync_card_to_vector_index"
)
async def test_phase0_emits_card_saved(mock_sync, db_session):
    """Phase 0 should save the card and emit card_saved as the first event."""
    payload = ZettelCardCreate(title="Test Card", content="Some content")
    stream = ZettelCreationStream(payload, db_session_factory=lambda: db_session)

    events = []
    async for sse in stream.run_phase0():
        events.append(sse)

    parsed = _parse_sse_events(events)
    assert len(parsed) >= 1
    event_name, data = parsed[0]
    assert event_name == "card_saved"
    assert data["title"] == "Test Card"
    assert "id" in data
    assert stream.card_id is not None


@pytest.mark.asyncio
@patch(
    "alfred.services.zettelkasten_service.ZettelkastenService._try_sync_card_to_vector_index"
)
async def test_phase0_card_persisted_in_db(mock_sync, db_session):
    """The card should actually exist in the database after Phase 0."""
    payload = ZettelCardCreate(title="Persisted Card", content="Content here")
    stream = ZettelCreationStream(payload, db_session_factory=lambda: db_session)

    async for _ in stream.run_phase0():
        pass

    card = db_session.get(ZettelCard, stream.card_id)
    assert card is not None
    assert card.title == "Persisted Card"
    assert card.content == "Content here"


@pytest.mark.asyncio
async def test_phase0_error_emits_error_event():
    """If card save fails, Phase 0 should emit error event, not crash."""
    payload = ZettelCardCreate(title="Error Card", content="Content")

    def bad_factory():
        raise RuntimeError("DB connection failed")

    stream = ZettelCreationStream(payload, db_session_factory=bad_factory)

    events = []
    async for sse in stream.run_phase0():
        events.append(sse)

    parsed = _parse_sse_events(events)
    assert len(parsed) == 1
    event_name, data = parsed[0]
    assert event_name == "error"
    assert "card_save" in data["step"]


@pytest.mark.asyncio
async def test_sse_format():
    """_sse helper should produce correct SSE format."""
    result = _sse("test_event", {"key": "value"})
    assert result == 'event: test_event\ndata: {"key": "value"}\n\n'


@pytest.mark.asyncio
@patch(
    "alfred.services.zettelkasten_service.ZettelkastenService._try_sync_card_to_vector_index"
)
async def test_full_run_emits_card_saved_then_done(mock_sync, db_session):
    """Full run() should emit card_saved first and done last."""
    payload = ZettelCardCreate(title="Full Run Test", content="Content")
    stream = ZettelCreationStream(payload, db_session_factory=lambda: db_session)

    events = []
    async for sse in stream.run():
        events.append(sse)

    parsed = _parse_sse_events(events)
    event_names = [e[0] for e in parsed]

    assert event_names[0] == "card_saved"
    assert event_names[-1] == "done"


@pytest.mark.asyncio
@patch(
    "alfred.services.zettelkasten_service.ZettelkastenService._try_sync_card_to_vector_index"
)
async def test_full_run_done_contains_card_info(mock_sync, db_session):
    """The done event should include the card id and title."""
    payload = ZettelCardCreate(title="Info Card", content="Details")
    stream = ZettelCreationStream(payload, db_session_factory=lambda: db_session)

    events = []
    async for sse in stream.run():
        events.append(sse)

    parsed = _parse_sse_events(events)
    done_event = [e for e in parsed if e[0] == "done"]
    assert len(done_event) == 1
    done_data = done_event[0][1]
    assert done_data["card"]["id"] is not None
    assert done_data["card"]["title"] == "Info Card"


@pytest.mark.asyncio
async def test_full_run_on_phase0_failure_emits_done_with_error():
    """If Phase 0 fails, run() should emit error then done with null card."""
    payload = ZettelCardCreate(title="Fail Card", content="Content")

    def bad_factory():
        raise RuntimeError("DB down")

    stream = ZettelCreationStream(payload, db_session_factory=bad_factory)

    events = []
    async for sse in stream.run():
        events.append(sse)

    parsed = _parse_sse_events(events)
    event_names = [e[0] for e in parsed]

    assert "error" in event_names
    assert event_names[-1] == "done"
    done_data = parsed[-1][1]
    assert done_data["card"] is None
    assert done_data["stats"]["error"] == "card_save_failed"
