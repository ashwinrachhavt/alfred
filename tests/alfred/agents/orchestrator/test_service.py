"""Tests for AgentService — OpenAI streaming agent with tool calls.

These tests verify the current AsyncOpenAI-based AgentService (not the
deprecated LangGraph orchestrator). They mock the OpenAI client to test
SSE event generation, tool dispatch, and error handling.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def _make_chunk(*, content: str | None = None, tool_calls: list | None = None):
    """Build a fake OpenAI streaming chunk."""
    delta = MagicMock()
    delta.content = content
    delta.tool_calls = tool_calls or []
    # No reasoning on standard models
    delta.reasoning = None
    delta.reasoning_content = None

    choice = MagicMock()
    choice.delta = delta

    chunk = MagicMock()
    chunk.choices = [choice]
    return chunk


async def _async_iter(items):
    for item in items:
        yield item


@pytest.mark.asyncio
async def test_stream_turn_yields_token_and_done():
    """Basic turn: model responds with text, we get token + done events."""
    from alfred.services.agent.service import AgentService

    chunks = [
        _make_chunk(content="Hello "),
        _make_chunk(content="world!"),
    ]
    mock_stream = _async_iter(chunks)

    mock_client = AsyncMock()
    mock_client.chat.completions.create = AsyncMock(return_value=mock_stream)

    with patch("alfred.services.agent.service._make_client", return_value=mock_client):
        service = AgentService(db=MagicMock())
        events = []
        async for event in service.stream_turn(message="hi"):
            events.append(event)

    event_text = "".join(events)
    assert "event: token" in event_text
    assert "Hello world!" in event_text
    assert "event: done" in event_text


@pytest.mark.asyncio
async def test_stream_turn_yields_tool_events():
    """When the model calls a tool, we get tool_start + tool_result + done."""
    from alfred.services.agent.service import AgentService

    # First response: tool call
    tc_delta = MagicMock()
    tc_delta.index = 0
    tc_delta.id = "call_abc"
    tc_delta.function = MagicMock()
    tc_delta.function.name = "search_kb"
    tc_delta.function.arguments = '{"query": "test"}'

    tool_chunk = _make_chunk(tool_calls=[tc_delta])

    # Second response: final answer
    answer_chunk = _make_chunk(content="Found results.")

    mock_client = AsyncMock()
    # First call returns tool call, second returns answer
    mock_client.chat.completions.create = AsyncMock(
        side_effect=[
            _async_iter([tool_chunk]),
            _async_iter([answer_chunk]),
        ]
    )

    mock_tool_result = {"results": [{"id": 1, "title": "Test"}]}

    with (
        patch("alfred.services.agent.service._make_client", return_value=mock_client),
        patch(
            "alfred.services.agent.service.execute_tool",
            new_callable=AsyncMock,
            return_value=mock_tool_result,
        ),
    ):
        service = AgentService(db=MagicMock())
        events = []
        async for event in service.stream_turn(message="search"):
            events.append(event)

    event_text = "".join(events)
    assert "event: tool_start" in event_text
    assert "event: tool_result" in event_text
    assert "event: done" in event_text


@pytest.mark.asyncio
async def test_stream_turn_handles_tool_timeout():
    """Tool timeout yields an error result, not a crash."""
    from alfred.services.agent.service import AgentService

    tc_delta = MagicMock()
    tc_delta.index = 0
    tc_delta.id = "call_timeout"
    tc_delta.function = MagicMock()
    tc_delta.function.name = "search_kb"
    tc_delta.function.arguments = '{"query": "slow"}'

    tool_chunk = _make_chunk(tool_calls=[tc_delta])
    answer_chunk = _make_chunk(content="Sorry, search timed out.")

    mock_client = AsyncMock()
    mock_client.chat.completions.create = AsyncMock(
        side_effect=[
            _async_iter([tool_chunk]),
            _async_iter([answer_chunk]),
        ]
    )

    with (
        patch("alfred.services.agent.service._make_client", return_value=mock_client),
        patch(
            "alfred.services.agent.service.execute_tool",
            new_callable=AsyncMock,
            side_effect=TimeoutError(),
        ),
    ):
        service = AgentService(db=MagicMock())
        events = []
        async for event in service.stream_turn(message="search"):
            events.append(event)

    event_text = "".join(events)
    # Should still complete with done, tool_result should contain error
    assert "event: tool_result" in event_text
    assert "timed out" in event_text
    assert "event: done" in event_text


@pytest.mark.asyncio
async def test_stream_turn_error_yields_error_event():
    """If OpenAI call fails, an error SSE event is emitted."""
    from alfred.services.agent.service import AgentService

    mock_client = AsyncMock()
    mock_client.chat.completions.create = AsyncMock(side_effect=RuntimeError("API down"))

    with patch("alfred.services.agent.service._make_client", return_value=mock_client):
        service = AgentService(db=MagicMock())
        events = []
        async for event in service.stream_turn(message="hi"):
            events.append(event)

    event_text = "".join(events)
    assert "event: error" in event_text
    assert "event: done" in event_text
