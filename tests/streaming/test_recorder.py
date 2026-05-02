"""Tests for RunRecorder — seq monotonicity, flush policy, fan-out, lifecycle."""

from __future__ import annotations

from uuid import uuid4

import pytest
from sqlmodel import Session, select

from alfred.models.streaming import AgentRunEventRow, AgentRunRow
from alfred.streaming.events import AnyRunEvent
from alfred.streaming.recorder import RunRecorder


class RecordingConsumer:
    """Test double — records every event it receives in order."""

    def __init__(self) -> None:
        self.events: list[AnyRunEvent] = []
        self.terminal: AnyRunEvent | None = None

    def on_event(self, event: AnyRunEvent) -> None:
        self.events.append(event)

    def on_run_finished(self, terminal: AnyRunEvent) -> None:
        self.terminal = terminal


@pytest.mark.asyncio
async def test_recorder_creates_run_row(session: Session) -> None:
    recorder = RunRecorder.start(
        session, run_type="chat_turn", thread_id=None,
        model_id="gpt-5.4-mini", active_lens=None,
    )
    assert recorder.run_id is not None
    row = session.exec(select(AgentRunRow).where(AgentRunRow.id == recorder.run_id)).one()
    assert row.status == "running"
    assert row.run_type == "chat_turn"


@pytest.mark.asyncio
async def test_recorder_assigns_monotonic_seq(session: Session) -> None:
    recorder = RunRecorder.start(session, run_type="chat_turn")
    msg_id = uuid4()
    seqs: list[int] = []
    async with recorder:
        for i in range(5):
            evt = await recorder.emit_delta(message_id=msg_id, delta_text=f"t{i}")
            seqs.append(evt.seq)
    # run.started is seq 0; five deltas are 1..5; run.finished is 6.
    assert seqs == [1, 2, 3, 4, 5]


@pytest.mark.asyncio
async def test_recorder_flushes_buffer_to_db(session: Session) -> None:
    recorder = RunRecorder.start(session, run_type="chat_turn")
    msg_id = uuid4()
    async with recorder:
        await recorder.emit_message_started(message_id=msg_id)
        for i in range(10):
            await recorder.emit_delta(message_id=msg_id, delta_text=str(i))
    rows = session.exec(
        select(AgentRunEventRow).where(AgentRunEventRow.run_id == recorder.run_id)
        .order_by(AgentRunEventRow.seq)
    ).all()
    event_types = [r.event_type for r in rows]
    assert event_types[0] == "run.started"
    assert event_types[1] == "message.started"
    assert event_types[-1] == "run.finished"
    assert event_types.count("message.delta") == 10


@pytest.mark.asyncio
async def test_recorder_fans_out_to_consumer(session: Session) -> None:
    recorder = RunRecorder.start(session, run_type="chat_turn")
    consumer = RecordingConsumer()
    recorder.attach(consumer)
    msg_id = uuid4()
    async with recorder:
        await recorder.emit_delta(message_id=msg_id, delta_text="hi")
    assert [e.event_type for e in consumer.events] == [
        "run.started", "message.delta", "run.finished",
    ]
    assert consumer.terminal is not None
    assert consumer.terminal.event_type == "run.finished"


@pytest.mark.asyncio
async def test_recorder_terminal_on_error(session: Session) -> None:
    recorder = RunRecorder.start(session, run_type="chat_turn")
    consumer = RecordingConsumer()
    recorder.attach(consumer)
    msg_id = uuid4()
    with pytest.raises(ValueError):
        async with recorder:
            await recorder.emit_delta(message_id=msg_id, delta_text="boom")
            raise ValueError("simulated producer failure")

    types = [e.event_type for e in consumer.events]
    assert types[-1] == "run.errored"

    rows = session.exec(
        select(AgentRunEventRow).where(AgentRunEventRow.run_id == recorder.run_id)
        .order_by(AgentRunEventRow.seq)
    ).all()
    assert rows[-1].event_type == "run.errored"

    run = session.exec(select(AgentRunRow).where(AgentRunRow.id == recorder.run_id)).one()
    assert run.status == "errored"


@pytest.mark.asyncio
async def test_significant_event_forces_flush(session: Session) -> None:
    """Non-delta events must be durable immediately."""
    recorder = RunRecorder.start(session, run_type="chat_turn")
    tool_id = "test-c1"
    await recorder.emit_tool_started(tool_call_id=tool_id, tool_name="search_kb", args_preview={"q": "x"})
    rows = session.exec(
        select(AgentRunEventRow).where(AgentRunEventRow.run_id == recorder.run_id)
    ).all()
    types = {r.event_type for r in rows}
    assert "tool.started" in types
    await recorder.aclose()


@pytest.mark.asyncio
async def test_parent_run_id_for_nested(session: Session) -> None:
    parent = RunRecorder.start(session, run_type="chat_turn")
    child = RunRecorder.start(session, run_type="tool_call", parent=parent)
    async with parent:
        async with child:
            tool_id = "test-c2"
            await child.emit_tool_started(tool_call_id=tool_id, tool_name="search_kb", args_preview={})
    child_row = session.exec(select(AgentRunRow).where(AgentRunRow.id == child.run_id)).one()
    assert child_row.parent_run_id == parent.run_id
