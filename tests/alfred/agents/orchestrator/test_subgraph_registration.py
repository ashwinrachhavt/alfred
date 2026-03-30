"""Tests for registering RAG and Writer sub-graphs as tools."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from alfred.agents.orchestrator.registry import ToolRegistry
from alfred.agents.orchestrator.tools.subgraphs import register_subgraphs


def test_register_subgraphs_adds_two_tools():
    registry = ToolRegistry()

    mock_rag_graph = MagicMock()
    mock_writer_graph = MagicMock()

    with patch(
        "alfred.agents.orchestrator.tools.subgraphs.build_agent_graph",
        return_value=mock_rag_graph,
    ), patch(
        "alfred.agents.orchestrator.tools.subgraphs.build_writer_graph",
        return_value=mock_writer_graph,
    ):
        register_subgraphs(registry)

    assert "research_topic" in registry.tools
    assert "compose_writing" in registry.tools
    assert len(registry.tools) == 2


def test_research_topic_tool_calls_rag_graph():
    registry = ToolRegistry()

    mock_rag_graph = MagicMock()
    mock_rag_graph.invoke.return_value = {
        "messages": [MagicMock(content="RAG answer about LangGraph")]
    }
    mock_writer_graph = MagicMock()

    with patch(
        "alfred.agents.orchestrator.tools.subgraphs.build_agent_graph",
        return_value=mock_rag_graph,
    ), patch(
        "alfred.agents.orchestrator.tools.subgraphs.build_writer_graph",
        return_value=mock_writer_graph,
    ):
        register_subgraphs(registry)

    result = registry.execute("research_topic", {"query": "What is LangGraph?", "mode": "concise"})
    assert "LangGraph" in result
    mock_rag_graph.invoke.assert_called_once()


def test_compose_writing_tool_calls_writer_graph():
    registry = ToolRegistry()

    mock_rag_graph = MagicMock()
    mock_writer_graph = MagicMock()
    mock_writer_graph.invoke.return_value = {"output": "A well-crafted LinkedIn post."}

    with patch(
        "alfred.agents.orchestrator.tools.subgraphs.build_agent_graph",
        return_value=mock_rag_graph,
    ), patch(
        "alfred.agents.orchestrator.tools.subgraphs.build_writer_graph",
        return_value=mock_writer_graph,
    ):
        register_subgraphs(registry)

    result = registry.execute("compose_writing", {
        "instruction": "Write a LinkedIn post about AI agents",
        "preset": "linkedin",
    })
    assert "LinkedIn" in result
    mock_writer_graph.invoke.assert_called_once()
