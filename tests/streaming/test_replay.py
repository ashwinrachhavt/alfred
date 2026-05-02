"""Tests for ReplayEngine skeleton.

Phase 0: load events for a run and yield them in seq order.
Phase 5 adds snapshot fast-forward, AG-UI projection, and speed-controlled playback.
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from sqlmodel import Session

from alfred.streaming.recorder import RunRecorder
from alfred.streaming.replay import ReplayEngine


@pytest.mark.asyncio
async def test_replay_yields_events_in_seq_order(session: Session):
    recorder = RunRecorder.start(session, run_type="chat_turn")
    msg_id = uuid4()
    async with recorder:
        for i in range(5):
            await recorder.emit_delta(message_id=msg_id, delta_text=str(i))
    engine = ReplayEngine(session)
    seqs: list[int] = []
    async for evt in engine.replay(recorder.run_id):
        seqs.append(evt.seq)
    assert seqs == sorted(seqs)
    assert seqs[0] == 0
    assert seqs[-1] >= len(seqs) - 1


@pytest.mark.asyncio
async def test_replay_unknown_run_yields_nothing(session: Session):
    engine = ReplayEngine(session)
    events = [e async for e in engine.replay(uuid4())]
    assert events == []


@pytest.mark.asyncio
async def test_replay_honors_target_seq(session: Session):
    recorder = RunRecorder.start(session, run_type="chat_turn")
    msg_id = uuid4()
    async with recorder:
        for i in range(10):
            await recorder.emit_delta(message_id=msg_id, delta_text=str(i))
    engine = ReplayEngine(session)
    events = [e async for e in engine.replay(recorder.run_id, target_seq=3)]
    assert all(e.seq <= 3 for e in events)
