"""Round-trip + discriminator tests for RunEvent models.

Spec: docs/superpowers/specs/2026-05-01-streaming-revamp-design.md section 4
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

import pytest
from pydantic import TypeAdapter, ValidationError

from alfred.streaming.events import (
    AnyRunEvent,
    ApprovalRequired,
    ApprovalResolved,
    MessageDelta,
    MessageFinished,
    MessageStarted,
    ProgressUpdate,
    RunCancelled,
    RunErrored,
    RunFinished,
    RunStarted,
    StateDelta,
    StateSnapshot,
    ThinkingDelta,
    ThinkingFinished,
    ToolArgsDelta,
    ToolArgsFinished,
    ToolResult,
    ToolStarted,
)


RUN_ID = UUID("00000000-0000-4000-8000-000000000001")
MSG_ID = UUID("00000000-0000-4000-8000-000000000002")
TOOL_ID = UUID("00000000-0000-4000-8000-000000000003")
APPROVAL_ID = UUID("00000000-0000-4000-8000-000000000004")
NOW = datetime(2026, 5, 1, 12, 0, 0, tzinfo=UTC)


def _roundtrip(evt):
    adapter = TypeAdapter(AnyRunEvent)
    raw = adapter.dump_python(evt, mode="json")
    return adapter.validate_python(raw)


def test_run_started_roundtrip():
    evt = RunStarted(
        run_id=RUN_ID, seq=0, emitted_at=NOW,
        parent_run_id=None, run_type="chat_turn",
        thread_id=7, user_id=None, input_summary="hello",
        model_id="gpt-5.4-mini", active_lens=None,
    )
    back = _roundtrip(evt)
    assert isinstance(back, RunStarted)
    assert back.run_type == "chat_turn"
    assert back.event_type == "run.started"


def test_run_finished_roundtrip():
    evt = RunFinished(
        run_id=RUN_ID, seq=42, emitted_at=NOW,
        duration_ms=1234, tokens_in=100, tokens_out=200, cost_usd=0.002,
    )
    back = _roundtrip(evt)
    assert isinstance(back, RunFinished)
    assert back.event_type == "run.finished"


def test_run_errored_roundtrip():
    evt = RunErrored(
        run_id=RUN_ID, seq=5, emitted_at=NOW,
        error_type="TimeoutError", error_message="tool timed out",
    )
    assert isinstance(_roundtrip(evt), RunErrored)


def test_run_cancelled_roundtrip():
    evt = RunCancelled(run_id=RUN_ID, seq=3, emitted_at=NOW, reason="client_disconnected")
    assert _roundtrip(evt).event_type == "run.cancelled"


def test_message_lifecycle_roundtrip():
    for evt in (
        MessageStarted(run_id=RUN_ID, seq=1, emitted_at=NOW, message_id=MSG_ID, role="assistant"),
        MessageDelta(run_id=RUN_ID, seq=2, emitted_at=NOW, message_id=MSG_ID, delta_text="hi"),
        MessageFinished(run_id=RUN_ID, seq=3, emitted_at=NOW, message_id=MSG_ID, final_text="hi", token_count=1),
    ):
        assert _roundtrip(evt) == evt


def test_thinking_channel_roundtrip():
    d = ThinkingDelta(run_id=RUN_ID, seq=1, emitted_at=NOW, message_id=MSG_ID, delta_text="...")
    f = ThinkingFinished(run_id=RUN_ID, seq=2, emitted_at=NOW, message_id=MSG_ID, full_text="...")
    assert _roundtrip(d) == d
    assert _roundtrip(f) == f


def test_tool_lifecycle_roundtrip():
    events = (
        ToolStarted(
            run_id=RUN_ID, seq=1, emitted_at=NOW,
            tool_call_id=TOOL_ID, tool_name="search_kb",
            parent_message_id=MSG_ID, args_preview={"q": "foo"},
        ),
        ToolArgsDelta(run_id=RUN_ID, seq=2, emitted_at=NOW, tool_call_id=TOOL_ID, delta_json='{"q":'),
        ToolArgsFinished(run_id=RUN_ID, seq=3, emitted_at=NOW, tool_call_id=TOOL_ID, full_args={"q": "foo"}),
        ToolResult(
            run_id=RUN_ID, seq=4, emitted_at=NOW,
            tool_call_id=TOOL_ID, result_json={"hits": []}, duration_ms=120, status="ok",
        ),
    )
    for evt in events:
        assert _roundtrip(evt) == evt


def test_state_delta_ops():
    for op in ("set", "append", "merge", "remove"):
        evt = StateDelta(run_id=RUN_ID, seq=1, emitted_at=NOW, key="artifacts", op=op, value={"id": 1})
        assert _roundtrip(evt).op == op


def test_state_snapshot_roundtrip():
    evt = StateSnapshot(
        run_id=RUN_ID, seq=99, emitted_at=NOW,
        state={"artifacts": [], "plan": []},
    )
    assert _roundtrip(evt).state == {"artifacts": [], "plan": []}


def test_progress_and_approval_roundtrip():
    events = (
        ProgressUpdate(run_id=RUN_ID, seq=1, emitted_at=NOW, stage="embedding", message="half done", pct_complete=0.5),
        ApprovalRequired(
            run_id=RUN_ID, seq=2, emitted_at=NOW,
            approval_id=APPROVAL_ID, action="publish", payload={"title": "x"}, reason="manual review",
        ),
        ApprovalResolved(
            run_id=RUN_ID, seq=3, emitted_at=NOW,
            approval_id=APPROVAL_ID, decision="approved", resolved_by="user",
        ),
    )
    for evt in events:
        assert _roundtrip(evt) == evt


def test_discriminator_rejects_unknown_event_type():
    adapter = TypeAdapter(AnyRunEvent)
    with pytest.raises(ValidationError):
        adapter.validate_python(
            {"event_type": "bogus.thing", "run_id": str(RUN_ID), "seq": 0, "emitted_at": NOW.isoformat()}
        )


def test_tool_result_status_enum():
    with pytest.raises(ValidationError):
        ToolResult(
            run_id=RUN_ID, seq=1, emitted_at=NOW,
            tool_call_id=TOOL_ID, result_json={}, duration_ms=1, status="weird",
        )
