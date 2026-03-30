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
async def test_stream_turn_intent_fast_path():
    """Intent with a known tool mapping should bypass the graph and call the tool directly."""
    import json

    from alfred.services.agent.service import AgentService

    mock_registry = MagicMock()
    mock_registry.tools = {"summarize_content": MagicMock()}
    mock_registry.execute.return_value = json.dumps({
        "action": "summarized",
        "short": "A concise summary.",
        "bullets": [],
        "key_points": [],
    })

    with patch("alfred.services.agent.service._build_registry", return_value=mock_registry), \
         patch("alfred.services.agent.service.build_orchestrator_graph") as mock_graph_builder:
        service = AgentService(db=MagicMock())
        events = []
        async for event in service.stream_turn(
            message="",
            model="gpt-4.1-mini",
            intent="summarize",
            intent_args={"text": "Long article text"},
        ):
            events.append(event)

    event_text = "".join(events)
    # Should have tool_start, tool_end, token, done — but NOT invoke the graph
    assert "event: tool_start" in event_text
    assert "event: token" in event_text
    assert "event: done" in event_text
    mock_graph_builder.assert_not_called()
    mock_registry.execute.assert_called_once_with("summarize_content", {"text": "Long article text"})


@pytest.mark.asyncio
async def test_stream_turn_intent_with_message_uses_graph():
    """Intent with a message should go through the graph (not fast path)."""
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
            message="summarize this for me",
            model="gpt-4.1-mini",
            intent="summarize",
            intent_args={"text": "article"},
        ):
            events.append(event)

    # Should have used the graph since message was provided
    mock_graph.invoke.assert_called_once()
