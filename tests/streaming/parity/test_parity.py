"""Phase 1 parity — MessageProjector output matches v1 _persist_message shape."""

from __future__ import annotations

import pytest
from sqlmodel import Session, select

from alfred.models.thinking import AgentMessageRow, ThinkingSessionRow
from alfred.streaming.producers.agent_producer import AgentProducer
from alfred.streaming.projectors.message_row import MessageProjector
from alfred.streaming.recorder import RunRecorder

from .fixtures import PARITY_FIXTURES, ParityFixture


class _FakeAgentService:
    """Fake agent service that yields a pre-scripted event stream."""

    def __init__(self, script: list[tuple[str, dict, str]]) -> None:
        self._script = script

    async def stream_turn(self, **_kwargs):
        """Yield scripted events."""
        for tup in self._script:
            yield tup


@pytest.mark.asyncio
@pytest.mark.parametrize("fixture", PARITY_FIXTURES, ids=[f.id for f in PARITY_FIXTURES])
async def test_parity(fixture: ParityFixture, session: Session) -> None:
    """Verify MessageProjector produces the same field values as v1 _persist_message."""
    # Create a thread for this fixture
    thread = ThinkingSessionRow(title=fixture.id, session_type="agent", status="active")
    session.add(thread)
    session.commit()
    session.refresh(thread)

    # Run the scripted turn through the v2 path
    service = _FakeAgentService(fixture.script)
    producer = AgentProducer(
        service=service,
        message="x",
        thread_id=thread.id,
        model=fixture.model,
        lens=fixture.lens,
    )
    recorder = RunRecorder.start(
        session,
        run_type="chat_turn",
        thread_id=thread.id,
        model_id=fixture.model,
        active_lens=fixture.lens,
    )
    projector = MessageProjector(session=session)
    recorder.attach(projector)

    async with recorder:
        async for evt in producer.stream():
            await recorder.emit_raw(evt)

    # Check persisted row
    rows = session.exec(
        select(AgentMessageRow).where(AgentMessageRow.thread_id == thread.id)
    ).all()

    if fixture.expected is None:
        # No row should have been written
        assert len(rows) == 0, f"expected no row for {fixture.id}; got {rows}"
        return

    assert len(rows) == 1, f"expected 1 row for {fixture.id}; got {len(rows)}"
    row = rows[0]
    exp = fixture.expected

    # Assert all persisted fields match expected
    assert row.role == "assistant"
    assert row.thread_id == thread.id
    assert row.content == exp.get("content", "")
    assert row.reasoning_traces == exp.get("reasoning_traces")
    assert row.tool_calls == exp.get("tool_calls")
    assert row.artifacts == exp.get("artifacts")
    assert row.related_cards == exp.get("related_cards")
    assert row.gaps == exp.get("gaps")
    assert row.active_lens == fixture.lens
    assert row.model_used == fixture.model
    assert row.projected_from_events is True
