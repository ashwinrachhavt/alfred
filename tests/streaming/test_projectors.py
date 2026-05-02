"""Tests for projector skeletons.

Phase 0 asserts interface conformance + basic mapping. Phase 1 will add full
MessageProjector row-writing tests; Phase 6 adds full state materialization.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlmodel import Session, select

from alfred.models.streaming import AgentRunSnapshotRow
from alfred.streaming.consumers import EventConsumer
from alfred.streaming.events import MessageDelta, RunStarted
from alfred.streaming.projectors.message_row import MessageProjector
from alfred.streaming.projectors.snapshot import SnapshotProjector
from alfred.streaming.projectors.wire_agui import AGUIProjector
from alfred.streaming.recorder import RunRecorder

NOW = datetime(2026, 5, 1, 12, 0, 0, tzinfo=UTC)


def test_projectors_implement_event_consumer():
    wire = AGUIProjector()
    msg = MessageProjector(session=None)
    snap = SnapshotProjector(session=None)
    assert isinstance(wire, EventConsumer)
    assert isinstance(msg, EventConsumer)
    assert isinstance(snap, EventConsumer)


def test_agui_projector_returns_frames_for_each_event():
    wire = AGUIProjector()
    evt = MessageDelta(run_id=uuid4(), seq=1, emitted_at=NOW, message_id=uuid4(), delta_text="hi")
    frames = wire.frames_for(evt)
    assert isinstance(frames, list)
    assert len(frames) == 1
    assert frames[0]["event"] == "TEXT_MESSAGE_CHUNK"
    assert frames[0]["data"]["delta"] == "hi"


def test_agui_projector_run_started_root_vs_nested():
    wire = AGUIProjector()
    root_evt = RunStarted(
        run_id=uuid4(), seq=0, emitted_at=NOW,
        parent_run_id=None, run_type="chat_turn",
    )
    child_evt = RunStarted(
        run_id=uuid4(), seq=0, emitted_at=NOW,
        parent_run_id=uuid4(), run_type="tool_call",
    )
    assert wire.frames_for(root_evt)[0]["event"] == "RUN_STARTED"
    assert wire.frames_for(child_evt)[0]["event"] == "STEP_STARTED"


@pytest.mark.asyncio
async def test_snapshot_projector_writes_terminal_row(session: Session):
    recorder = RunRecorder.start(session, run_type="chat_turn")
    snap = SnapshotProjector(session=session)
    recorder.attach(snap)
    msg_id = uuid4()
    async with recorder:
        await recorder.emit_message_started(message_id=msg_id)
        await recorder.emit_delta(message_id=msg_id, delta_text="hi")
    rows = session.exec(
        select(AgentRunSnapshotRow).where(AgentRunSnapshotRow.run_id == recorder.run_id)
        .order_by(AgentRunSnapshotRow.up_to_seq)
    ).all()
    assert len(rows) >= 1
    terminal = rows[-1]
    assert terminal.up_to_seq > 0
