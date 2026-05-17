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
from alfred.models.thinking import AgentMessageRow, ThinkingSessionRow
from alfred.streaming.consumers import EventConsumer
from alfred.streaming.events import (
    MessageDelta,
    RunStarted,
    StateDelta,
    ThinkingDelta,
    ToolResult,
    ToolStarted,
)
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


def test_agui_projector_returns_canonical_camel_case_event_objects():
    wire = AGUIProjector()
    message_id = uuid4()
    evt = MessageDelta(run_id=uuid4(), seq=1, emitted_at=NOW, message_id=message_id, delta_text="hi")
    frames = wire.frames_for(evt)
    assert isinstance(frames, list)
    assert len(frames) == 1
    assert frames[0] == {
        "type": "TEXT_MESSAGE_CONTENT",
        "messageId": str(message_id),
        "delta": "hi",
    }


def test_agui_projector_run_started_root_vs_nested():
    wire = AGUIProjector()
    parent_run_id = uuid4()
    root_evt = RunStarted(
        run_id=uuid4(), seq=0, emitted_at=NOW,
        parent_run_id=None, run_type="chat_turn",
    )
    child_evt = RunStarted(
        run_id=uuid4(), seq=0, emitted_at=NOW,
        parent_run_id=parent_run_id, run_type="tool_call",
    )
    root = wire.frames_for(root_evt)[0]
    child = wire.frames_for(child_evt)[0]
    assert root["type"] == "RUN_STARTED"
    assert root["runId"] == str(root_evt.run_id)
    assert root["parentRunId"] is None
    assert child["type"] == "RUN_STARTED"
    assert child["runId"] == str(child_evt.run_id)
    assert child["parentRunId"] == str(parent_run_id)


def test_agui_projector_maps_reasoning_to_reasoning_events():
    wire = AGUIProjector()
    message_id = uuid4()
    evt = ThinkingDelta(
        run_id=uuid4(), seq=2, emitted_at=NOW,
        message_id=message_id, delta_text="checking assumptions",
    )

    assert wire.frames_for(evt) == [{
        "type": "REASONING_MESSAGE_CONTENT",
        "messageId": f"{message_id}::reasoning",
        "delta": "checking assumptions",
    }]


def test_agui_projector_expands_tool_started_with_args_preview():
    wire = AGUIProjector()
    evt = ToolStarted(
        run_id=uuid4(), seq=3, emitted_at=NOW,
        tool_call_id="call-1", tool_name="search_kb",
        parent_message_id=uuid4(), args_preview={"q": "epistemology"},
    )

    frames = wire.frames_for(evt)

    assert frames == [
        {
            "type": "TOOL_CALL_START",
            "toolCallId": "call-1",
            "toolCallName": "search_kb",
            "parentMessageId": str(evt.parent_message_id),
        },
        {
            "type": "TOOL_CALL_ARGS",
            "toolCallId": "call-1",
            "delta": '{"q":"epistemology"}',
        },
        {
            "type": "TOOL_CALL_END",
            "toolCallId": "call-1",
        },
    ]


def test_agui_projector_maps_state_delta_to_json_patch():
    wire = AGUIProjector()
    evt = StateDelta(
        run_id=uuid4(), seq=4, emitted_at=NOW,
        key="related_cards", op="set",
        value=[{"zettelId": 12, "title": "A"}],
    )

    assert wire.frames_for(evt) == [{
        "type": "STATE_DELTA",
        "delta": [{
            "op": "add",
            "path": "/relatedCards",
            "value": [{"zettelId": 12, "title": "A"}],
        }],
    }]


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


@pytest.mark.asyncio
async def test_message_projector_writes_assistant_row_on_run_finished(session: Session):
    """on_run_finished must INSERT an AgentMessageRow with projected_from_events=True."""
    thread = ThinkingSessionRow(title="t", session_type="agent", status="active")
    session.add(thread)
    session.commit()
    session.refresh(thread)

    recorder = RunRecorder.start(
        session, run_type="chat_turn", thread_id=thread.id,
        model_id="gpt-5.4-mini", active_lens="research",
    )
    projector = MessageProjector(session=session)
    recorder.attach(projector)
    msg_id = uuid4()
    async with recorder:
        await recorder.emit_message_started(message_id=msg_id)
        await recorder.emit_delta(message_id=msg_id, delta_text="Hello ")
        await recorder.emit_delta(message_id=msg_id, delta_text="world")

    rows = session.exec(
        select(AgentMessageRow).where(AgentMessageRow.thread_id == thread.id)
    ).all()
    assert len(rows) == 1
    r = rows[0]
    assert r.role == "assistant"
    assert r.content == "Hello world"
    assert r.active_lens == "research"
    assert r.model_used == "gpt-5.4-mini"
    assert r.run_id == recorder.run_id
    assert r.projected_from_events is True
    # reasoning + tool_calls + artifacts all absent → None
    assert r.reasoning_traces is None
    assert r.tool_calls is None
    assert r.artifacts is None
    # parts[] dual-write — single finalized streaming-text part
    assert r.parts is not None
    assert len(r.parts) == 1
    assert r.parts[0]["type"] == "text"
    assert r.parts[0]["text"] == "Hello world"
    assert r.parts[0]["state"] == "done"


@pytest.mark.asyncio
async def test_message_projector_captures_tool_calls_and_artifacts(session: Session):
    """tool_calls[] entries must use v1 shape: {call_id, tool, args, result, status}."""
    thread = ThinkingSessionRow(title="t", session_type="agent", status="active")
    session.add(thread)
    session.commit()
    session.refresh(thread)

    recorder = RunRecorder.start(session, run_type="chat_turn", thread_id=thread.id)
    projector = MessageProjector(session=session)
    recorder.attach(projector)
    tool_id = "test-tool-call-1"
    async with recorder:
        await recorder.emit_tool_started(
            tool_call_id=tool_id, tool_name="search_kb",
            args_preview={"q": "epistemology"},
        )
        await recorder.emit_raw(ToolResult(
            run_id=recorder.run_id, seq=0, emitted_at=datetime.now(UTC),
            tool_call_id=tool_id, result_json={"hits": ["z1", "z2"]},
            duration_ms=123, status="ok",
        ))
        await recorder.emit_raw(StateDelta(
            run_id=recorder.run_id, seq=0, emitted_at=datetime.now(UTC),
            key="artifacts", op="append",
            value={
                "type": "zettel", "action": "created",
                "zettel": {"id": 42, "title": "Belief vs knowledge",
                           "summary": "", "topic": "", "tags": []},
            },
        ))

    row = session.exec(
        select(AgentMessageRow).where(AgentMessageRow.thread_id == thread.id)
    ).one()
    assert row.tool_calls is not None
    assert len(row.tool_calls) == 1
    tc = row.tool_calls[0]
    # V1 LEGACY SHAPE: keys are call_id/tool (not tool_call_id/tool_name)
    assert tc["call_id"] == str(tool_id)
    assert tc["tool"] == "search_kb"
    assert tc["args"] == {"q": "epistemology"}
    assert tc["result"] == {"hits": ["z1", "z2"]}
    assert tc["status"] == "ok"
    # Artifact passes through unchanged
    assert row.artifacts == [{
        "type": "zettel", "action": "created",
        "zettel": {"id": 42, "title": "Belief vs knowledge",
                   "summary": "", "topic": "", "tags": []},
    }]
    # parts[] dual-write — tool part with output-available state
    assert row.parts is not None
    tool_parts = [p for p in row.parts if str(p.get("type", "")).startswith("tool-")]
    assert len(tool_parts) == 1
    tp = tool_parts[0]
    assert tp["type"] == "tool-search_kb"
    assert tp["toolCallId"] == str(tool_id)
    assert tp["state"] == "output-available"
    assert tp["input"] == {"q": "epistemology"}
    assert tp["output"] == {"hits": ["z1", "z2"]}


@pytest.mark.asyncio
async def test_message_projector_skips_row_when_no_content_and_no_tools(session: Session):
    """If the run produced no content, no tool calls, and no artifacts, skip the write.

    This matches v1 behavior at routes.py:246 where _persist_message is only called if
    assistant_content or tool_calls or artifacts were present.
    """
    thread = ThinkingSessionRow(title="t", session_type="agent", status="active")
    session.add(thread)
    session.commit()
    session.refresh(thread)

    recorder = RunRecorder.start(session, run_type="chat_turn", thread_id=thread.id)
    projector = MessageProjector(session=session)
    recorder.attach(projector)
    async with recorder:
        pass  # no events emitted

    rows = session.exec(
        select(AgentMessageRow).where(AgentMessageRow.thread_id == thread.id)
    ).all()
    assert len(rows) == 0
