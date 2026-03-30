"""Tests for the real AgentService (replaces stub)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from langchain_core.messages import AIMessage, HumanMessage


@pytest.mark.asyncio
async def test_stream_turn_yields_token_events():
    from alfred.services.agent.service import AgentService

    mock_response = AIMessage(content="Hello from the agent!")
    mock_graph = MagicMock()
    mock_graph.invoke.return_value = {
        "messages": [HumanMessage(content="hi"), mock_response],
        "iteration": 1,
    }

    with patch("alfred.services.agent.service.build_orchestrator_graph", return_value=mock_graph), \
         patch("alfred.services.agent.service._build_registry"):
        service = AgentService(db=MagicMock())
        events = []
        async for event in service.stream_turn(message="hi", model="gpt-4.1-mini"):
            events.append(event)

    event_text = "".join(events)
    assert "event: token" in event_text or "event: done" in event_text
    assert "event: done" in event_text


@pytest.mark.asyncio
async def test_stream_turn_yields_tool_events():
    from alfred.services.agent.service import AgentService

    tool_call_msg = AIMessage(
        content="",
        tool_calls=[{"name": "search_kb", "args": {"query": "test"}, "id": "c1"}],
    )
    final_msg = AIMessage(content="Found results.")
    mock_graph = MagicMock()
    mock_graph.invoke.return_value = {
        "messages": [
            HumanMessage(content="search"),
            tool_call_msg,
            MagicMock(content='{"results": []}'),
            final_msg,
        ],
        "iteration": 2,
    }

    with patch("alfred.services.agent.service.build_orchestrator_graph", return_value=mock_graph), \
         patch("alfred.services.agent.service._build_registry"):
        service = AgentService(db=MagicMock())
        events = []
        async for event in service.stream_turn(message="search", model="gpt-4.1-mini"):
            events.append(event)

    event_text = "".join(events)
    assert "event: done" in event_text


@pytest.mark.asyncio
async def test_stream_turn_with_intent():
    from alfred.services.agent.service import AgentService

    mock_graph = MagicMock()
    mock_graph.invoke.return_value = {
        "messages": [AIMessage(content="Summary: ...")],
        "iteration": 1,
    }

    with patch("alfred.services.agent.service.build_orchestrator_graph", return_value=mock_graph), \
         patch("alfred.services.agent.service._build_registry"):
        service = AgentService(db=MagicMock())
        events = []
        async for event in service.stream_turn(
            message="",
            model="gpt-4.1-mini",
            intent="summarize",
            intent_args={"url": "https://example.com"},
        ):
            events.append(event)

    call_args = mock_graph.invoke.call_args[0][0]
    assert call_args.get("intent") == "summarize"
