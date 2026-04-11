"""Tests for Alfred's orchestration graph."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from langchain_core.messages import HumanMessage

from alfred.agents.orchestrator.graph import build_orchestrator_graph


def _base_state(message: str) -> dict:
    return {
        "messages": [HumanMessage(content=message)],
        "thread_id": "thread-1",
        "user_id": "user-1",
        "model": "gpt-5.4",
        "phase": "routing",
        "active_agents": [],
        "plan": [],
        "task_results": [],
        "pending_approvals": [],
        "artifacts": [],
        "related_cards": [],
        "gaps": [],
        "final_response": None,
    }


def test_graph_compiles():
    graph = build_orchestrator_graph()
    assert graph is not None


def test_graph_has_expected_nodes():
    graph = build_orchestrator_graph()
    node_names = set(graph.get_graph().nodes.keys())
    assert {"planner", "direct_chat", "execute_task", "gather_results", "approval_gate", "writer", "finalizer"} <= node_names


@pytest.mark.asyncio
async def test_direct_chat_path_uses_fallback_response():
    graph = build_orchestrator_graph()

    result = await graph.ainvoke(_base_state("hello"))

    assert result["phase"] == "done"
    assert result["active_agents"] == ["chat"]
    assert result["final_response"] == "Alfred heard: hello"


@pytest.mark.asyncio
async def test_parallel_worker_results_are_synthesized():
    graph = build_orchestrator_graph()
    fake_worker = AsyncMock(
        side_effect=[
            {
                "task_id": "task-k",
                "agent": "knowledge",
                "objective": "search",
                "summary": "Internal context says LangGraph already exists in Alfred.",
                "artifacts": [],
                "related_cards": [],
                "gaps": [],
                "proposed_actions": [],
            },
            {
                "task_id": "task-c",
                "agent": "connection",
                "objective": "connect",
                "summary": "A connection worker found related notes about orchestration.",
                "artifacts": [],
                "related_cards": [],
                "gaps": [],
                "proposed_actions": [],
            },
        ]
    )

    with patch("alfred.agents.orchestrator.nodes.run_worker_task", fake_worker):
        result = await graph.ainvoke(
            _base_state("search my notes and connect related ideas about LangGraph")
        )

    assert fake_worker.await_count == 2
    assert len(result["plan"]) == 2
    assert len(result["task_results"]) == 2
    assert "### Knowledge" in result["final_response"]
    assert "### Connection" in result["final_response"]


@pytest.mark.asyncio
async def test_pending_approvals_flow_into_writer_output():
    graph = build_orchestrator_graph()
    fake_worker = AsyncMock(
        return_value={
            "task_id": "task-k",
            "agent": "knowledge",
            "objective": "search",
            "summary": "Found a strong synthesis worth saving.",
            "artifacts": [],
            "related_cards": [],
            "gaps": [],
            "proposed_actions": [
                {
                    "id": "approval-1",
                    "action": "create_zettel",
                    "reason": "This answer should become a new card.",
                    "payload": {"title": "LangGraph orchestration in Alfred"},
                }
            ],
        }
    )

    with patch("alfred.agents.orchestrator.nodes.run_worker_task", fake_worker):
        result = await graph.ainvoke(_base_state("search my knowledge and save the synthesis"))

    assert len(result["pending_approvals"]) == 1
    assert "### Proposed Actions" in result["final_response"]
    assert "create_zettel" in result["final_response"]
