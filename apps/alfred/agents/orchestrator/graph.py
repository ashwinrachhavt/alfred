"""Alfred orchestration graph.

Planner-driven flow:
planner -> direct_chat OR parallel execute_task branches -> gather_results
-> approval_gate -> writer -> finalizer.
"""

from __future__ import annotations

from typing import Any

from langgraph.graph import END, START, StateGraph

from alfred.agents.orchestrator.nodes import (
    approval_gate,
    direct_chat,
    execute_task,
    finalizer,
    gather_results,
    planner,
    route_after_planner,
    writer,
)
from alfred.agents.orchestrator.state import AlfredAgentState


def build_orchestrator_graph() -> Any:
    """Build and compile Alfred's planner-driven orchestrator graph."""

    workflow = StateGraph(AlfredAgentState)
    workflow.add_node("planner", planner)
    workflow.add_node("direct_chat", direct_chat)
    workflow.add_node("execute_task", execute_task)
    workflow.add_node("gather_results", gather_results)
    workflow.add_node("approval_gate", approval_gate)
    workflow.add_node("writer", writer)
    workflow.add_node("finalizer", finalizer)

    workflow.add_edge(START, "planner")
    workflow.add_conditional_edges("planner", route_after_planner, ["direct_chat", "execute_task"])
    workflow.add_edge("execute_task", "gather_results")
    workflow.add_edge("gather_results", "approval_gate")
    workflow.add_edge("approval_gate", "writer")
    workflow.add_edge("writer", "finalizer")
    workflow.add_edge("direct_chat", "finalizer")
    workflow.add_edge("finalizer", END)

    return workflow.compile()


__all__ = ["build_orchestrator_graph"]
