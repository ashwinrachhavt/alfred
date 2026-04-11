"""Ingest team -- Connector + Import + Enrichment agents."""

from __future__ import annotations

from langgraph.prebuilt import create_react_agent
from langgraph_supervisor import create_supervisor

from alfred.agents.tools.connector_tools import CONNECTOR_TOOLS
from alfred.agents.tools.enrichment_tools import ENRICHMENT_TOOLS
from alfred.agents.tools.import_tools import IMPORT_TOOLS
from alfred.core.llm_factory import get_chat_model


def build_ingest_team(*, model: str | None = None):
    """Build the Ingest team supervisor graph."""
    team_model = get_chat_model(model=model or "gpt-4.1-mini")

    connector_agent = create_react_agent(
        model=team_model,
        tools=CONNECTOR_TOOLS,
        name="connector_agent",
        prompt="You query external knowledge sources (Notion, Readwise, ArXiv, RSS, etc.) to find information. Use one tool at a time.",
    )

    import_agent = create_react_agent(
        model=team_model,
        tools=IMPORT_TOOLS,
        name="import_agent",
        prompt="You trigger batch imports from connectors and monitor their progress. Use one tool at a time.",
    )

    enrichment_agent = create_react_agent(
        model=team_model,
        tools=ENRICHMENT_TOOLS,
        name="enrichment_agent",
        prompt="You enrich documents with summaries, concept extraction, classification, and zettel decomposition. Use one tool at a time.",
    )

    workflow = create_supervisor(
        agents=[connector_agent, import_agent, enrichment_agent],
        model=team_model,
        prompt=(
            "You are the Ingest team supervisor. Route tasks to the appropriate agent:\n"
            "- connector_agent: Live-query external sources (Notion, ArXiv, RSS, etc.)\n"
            "- import_agent: Trigger batch imports or check import status\n"
            "- enrichment_agent: Summarize, classify, or decompose documents"
        ),
    )

    return workflow.compile(name="ingest_team")
