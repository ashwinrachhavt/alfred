"""Tests for AgentProducer — maps AgentService yield-tuples to typed RunEvents.

Producer is a pure adapter: given a scripted FakeAgentService that yields
(event_name, data, sse_str) tuples, it produces typed RunEvent objects with
placeholder run_id/seq (the recorder rewrites them via emit_raw).
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

import pytest

from alfred.streaming.events import (
    MessageDelta,
    MessageStarted,
    RunErrored,
    StateDelta,
    ThinkingDelta,
    ToolResult,
    ToolStarted,
)
from alfred.streaming.producers.agent_producer import AgentProducer


class FakeAgentService:
    """Test double — yields (event_name, data, sse_str) tuples like the real one."""

    def __init__(self, script: list[tuple[str, dict[str, Any], str]]) -> None:
        self._script = script

    async def stream_turn(self, **_kwargs: Any) -> AsyncIterator[tuple[str, dict[str, Any], str]]:
        for tup in self._script:
            yield tup


async def _collect(producer: AgentProducer) -> list:
    return [evt async for evt in producer.stream()]


@pytest.mark.asyncio
async def test_producer_maps_token_to_message_started_plus_delta() -> None:
    """First token emits MessageStarted; every token (incl. first) emits MessageDelta."""
    fake = FakeAgentService([
        ("token", {"content": "hello"}, ""),
        ("token", {"content": " world"}, ""),
        ("done", {"thread_id": "1"}, ""),
    ])
    producer = AgentProducer(
        service=fake, message="hi", thread_id=1, model="gpt-5.4-mini", lens=None,
    )
    events = await _collect(producer)
    types = [e.event_type for e in events]
    # MessageStarted precedes any MessageDelta
    assert types[0] == "message.started"
    # Both token tuples produce MessageDelta
    deltas = [e for e in events if isinstance(e, MessageDelta)]
    assert [d.delta_text for d in deltas] == ["hello", " world"]
    # All deltas share the same message_id as the MessageStarted
    started = next(e for e in events if isinstance(e, MessageStarted))
    assert all(d.message_id == started.message_id for d in deltas)


@pytest.mark.asyncio
async def test_producer_maps_reasoning_to_thinking_delta() -> None:
    fake = FakeAgentService([
        ("reasoning", {"content": "let me think"}, ""),
        ("reasoning", {"content": " about this"}, ""),
        ("done", {}, ""),
    ])
    producer = AgentProducer(
        service=fake, message="x", thread_id=1, model="o3", lens=None,
    )
    events = await _collect(producer)
    thinking = [e for e in events if isinstance(e, ThinkingDelta)]
    assert [t.delta_text for t in thinking] == ["let me think", " about this"]


@pytest.mark.asyncio
async def test_producer_stable_tool_uuid_across_start_and_result() -> None:
    """tool.started and tool.result for the same call_id must share tool_call_id UUID."""
    fake = FakeAgentService([
        ("tool_start", {"call_id": "c1", "tool": "search_kb", "args": {"q": "x"}}, ""),
        ("tool_result", {"call_id": "c1", "result": {"hits": 3}, "status": "ok"}, ""),
        ("done", {}, ""),
    ])
    producer = AgentProducer(
        service=fake, message="x", thread_id=1, model="gpt-5.4-mini", lens=None,
    )
    events = await _collect(producer)
    started = next(e for e in events if isinstance(e, ToolStarted))
    result = next(e for e in events if isinstance(e, ToolResult))
    assert started.tool_name == "search_kb"
    assert started.args_preview == {"q": "x"}
    assert result.status == "ok"
    assert result.result_json == {"hits": 3}
    # Critical: same call_id → same tool_call_id UUID
    assert started.tool_call_id == result.tool_call_id


@pytest.mark.asyncio
async def test_producer_maps_artifact_to_state_delta_append() -> None:
    fake = FakeAgentService([
        (
            "artifact",
            {
                "type": "zettel", "action": "created",
                "zettel": {"id": 42, "title": "T", "summary": "", "topic": "", "tags": []},
            },
            "",
        ),
        ("done", {}, ""),
    ])
    producer = AgentProducer(
        service=fake, message="x", thread_id=1, model="gpt-5.4-mini", lens=None,
    )
    events = await _collect(producer)
    state = next(e for e in events if isinstance(e, StateDelta))
    assert state.key == "artifacts"
    assert state.op == "append"
    assert state.value == {
        "type": "zettel", "action": "created",
        "zettel": {"id": 42, "title": "T", "summary": "", "topic": "", "tags": []},
    }


@pytest.mark.asyncio
async def test_producer_error_tuple_terminates_with_errored() -> None:
    """An ('error', ...) tuple becomes a terminal RunErrored event."""
    fake = FakeAgentService([
        ("token", {"content": "hi"}, ""),
        ("error", {"message": "upstream timeout"}, ""),
    ])
    producer = AgentProducer(
        service=fake, message="x", thread_id=1, model="gpt-5.4-mini", lens=None,
    )
    events = await _collect(producer)
    assert isinstance(events[-1], RunErrored)
    assert "upstream timeout" in events[-1].error_message
