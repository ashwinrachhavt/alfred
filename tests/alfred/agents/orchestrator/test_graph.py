"""Tests for the master orchestrator graph."""

from __future__ import annotations

import uuid
from unittest.mock import patch, MagicMock

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.tools import tool as lc_tool

from alfred.agents.orchestrator.graph import build_orchestrator_graph
from alfred.agents.orchestrator.registry import ToolRegistry


@lc_tool
def greet_tool(name: str) -> str:
    """Greet someone by name."""
    return f"Hello, {name}!"


def _make_registry_with_greet() -> ToolRegistry:
    reg = ToolRegistry()
    reg.register(greet_tool)
    return reg


def test_graph_compiles():
    registry = _make_registry_with_greet()
    graph = build_orchestrator_graph(registry, model="gpt-4.1-mini")
    assert graph is not None


def test_graph_has_expected_nodes():
    registry = _make_registry_with_greet()
    graph = build_orchestrator_graph(registry, model="gpt-4.1-mini")
    node_names = set(graph.get_graph().nodes.keys())
    assert "router" in node_names
    assert "tool_executor" in node_names


def test_graph_direct_response():
    registry = _make_registry_with_greet()
    mock_response = AIMessage(content="I can help with that!")

    with patch("alfred.agents.orchestrator.graph.get_chat_model") as mock_factory:
        mock_llm = mock_factory.return_value
        mock_llm.bind_tools.return_value = mock_llm
        mock_llm.invoke.return_value = mock_response

        graph = build_orchestrator_graph(registry, model="gpt-4.1-mini")
        result = graph.invoke({
            "messages": [HumanMessage(content="hello")],
            "thread_id": "test-1",
            "model": "gpt-4.1-mini",
            "iteration": 0,
        })

    assert len(result["messages"]) >= 2
    last_msg = result["messages"][-1]
    assert last_msg.content == "I can help with that!"


def test_graph_tool_call_then_response():
    registry = _make_registry_with_greet()

    tool_call_msg = AIMessage(
        content="",
        tool_calls=[{"name": "greet_tool", "args": {"name": "Ashwin"}, "id": "call_1"}],
    )
    final_msg = AIMessage(content="The greeting is: Hello, Ashwin!")

    call_count = 0

    def mock_invoke(messages, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return tool_call_msg
        return final_msg

    with patch("alfred.agents.orchestrator.graph.get_chat_model") as mock_factory:
        mock_llm = mock_factory.return_value
        mock_llm.bind_tools.return_value = mock_llm
        mock_llm.invoke.side_effect = mock_invoke

        graph = build_orchestrator_graph(registry, model="gpt-4.1-mini")
        result = graph.invoke({
            "messages": [HumanMessage(content="greet Ashwin")],
            "thread_id": "test-2",
            "model": "gpt-4.1-mini",
            "iteration": 0,
        })

    messages = result["messages"]
    assert any(isinstance(m, ToolMessage) for m in messages)
    assert messages[-1].content == "The greeting is: Hello, Ashwin!"


def test_graph_max_iterations():
    """Graph should stop after max iterations and force a final text response."""
    registry = _make_registry_with_greet()
    forced_final = AIMessage(content="I ran out of iterations but here is what I found.")

    def make_tool_call_msg():
        return AIMessage(
            content="",
            id=str(uuid.uuid4()),
            tool_calls=[{"name": "greet_tool", "args": {"name": "loop"}, "id": f"call_{uuid.uuid4().hex[:8]}"}],
        )

    with patch("alfred.agents.orchestrator.graph.get_chat_model") as mock_factory:
        mock_llm_with_tools = MagicMock()
        mock_llm_with_tools.invoke.side_effect = lambda msgs, **kw: make_tool_call_msg()

        mock_llm_plain = MagicMock()
        mock_llm_plain.bind_tools.return_value = mock_llm_with_tools
        mock_llm_plain.invoke.return_value = forced_final

        mock_factory.return_value = mock_llm_plain

        graph = build_orchestrator_graph(registry, model="gpt-4.1-mini", max_iterations=3)
        result = graph.invoke({
            "messages": [HumanMessage(content="loop forever")],
            "thread_id": "test-3",
            "model": "gpt-4.1-mini",
            "iteration": 0,
        })

    tool_messages = [m for m in result["messages"] if isinstance(m, ToolMessage)]
    assert len(tool_messages) <= 3
    last_msg = result["messages"][-1]
    assert isinstance(last_msg, AIMessage)
    assert last_msg.content
    assert not getattr(last_msg, "tool_calls", None)
