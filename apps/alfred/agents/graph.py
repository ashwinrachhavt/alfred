"""Top-level Alfred agent graph."""

from __future__ import annotations

from alfred.agents.orchestrator.graph import build_orchestrator_graph


def build_alfred_graph():
    """Build and compile Alfred's active orchestration graph."""

    return build_orchestrator_graph()


# Export for langgraph.json
alfred_graph = build_alfred_graph
