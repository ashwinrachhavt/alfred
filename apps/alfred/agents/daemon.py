"""Background daemon -- Celery periodic tasks for autonomous agent operation.

Same LangGraph graph invoked programmatically without the LLM supervisor.
"""

from __future__ import annotations

import logging

from celery import shared_task
from langchain_core.messages import HumanMessage

logger = logging.getLogger(__name__)


@shared_task(name="alfred.agents.daemon.ingest_watch")
def ingest_watch():
    """Check all connected sources for new content since last sync."""
    from alfred.agents.graph import build_alfred_graph
    graph = build_alfred_graph()
    result = graph.invoke({
        "messages": [HumanMessage(content="Check all connected sources for new content since last sync and import anything new.")],
        "user_id": "daemon",
        "intent": "import",
        "phase": "executing",
        "active_agents": ["ingest_team"],
        "knowledge_results": [],
        "research_results": [],
        "connector_results": [],
        "enrichment_results": [],
        "final_response": None,
        "artifacts": [],
    })
    logger.info("Daemon ingest_watch completed: %s", result.get("final_response", "")[:200])
    return {"status": "completed"}


@shared_task(name="alfred.agents.daemon.link_discovery")
def link_discovery(limit: int = 50):
    """Find cards with few links and generate suggestions."""
    from alfred.agents.graph import build_alfred_graph
    graph = build_alfred_graph()
    result = graph.invoke({
        "messages": [HumanMessage(content=f"Find the top {limit} zettel cards with the fewest links and suggest new connections for them.")],
        "user_id": "daemon",
        "intent": "connect",
        "phase": "executing",
        "active_agents": ["knowledge_team"],
        "knowledge_results": [],
        "research_results": [],
        "connector_results": [],
        "enrichment_results": [],
        "final_response": None,
        "artifacts": [],
    })
    logger.info("Daemon link_discovery completed")
    return {"status": "completed"}
