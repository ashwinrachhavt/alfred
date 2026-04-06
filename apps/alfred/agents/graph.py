"""Top-level Alfred supervisor graph."""

from __future__ import annotations

import logging

from langgraph.graph import END, START, StateGraph

from alfred.agents.chat import chat
from alfred.agents.router import router
from alfred.agents.state import AlfredState
from alfred.agents.synthesizer import synthesizer
from alfred.agents.teams.ingest_team import build_ingest_team
from alfred.agents.teams.knowledge_team import build_knowledge_team
from alfred.agents.teams.synthesis_team import build_synthesis_team

logger = logging.getLogger(__name__)


def build_alfred_graph():
    """Build and compile the Alfred multi-agent supervisor graph."""
    builder = StateGraph(AlfredState)

    builder.add_node("router", router)
    builder.add_node("chat", chat)  # direct conversational responses — no tools
    builder.add_node("ingest_team", build_ingest_team())
    builder.add_node("knowledge_team", build_knowledge_team())
    builder.add_node("synthesis_team", build_synthesis_team())
    builder.add_node("synthesizer", synthesizer)

    builder.add_edge(START, "router")
    # Router uses Command(goto=...) for dynamic routing — no static edges from router
    builder.add_edge("chat", END)  # chat responds directly, no synthesizer needed
    builder.add_edge("ingest_team", "synthesizer")
    builder.add_edge("knowledge_team", "synthesizer")
    builder.add_edge("synthesis_team", "synthesizer")
    builder.add_edge("synthesizer", END)

    return builder.compile()


# Export for langgraph.json — callable that returns the compiled graph
alfred_graph = build_alfred_graph
