"""Ingest team -- Connector + Import + Enrichment agents.

Uses GPT-4.1-mini for all agents (mostly tool dispatch, low reasoning needed).
"""

from __future__ import annotations

from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent
from langgraph_supervisor import create_supervisor

from alfred.agents.tools.connector_tools import CONNECTOR_TOOLS
from alfred.agents.tools.enrichment_tools import ENRICHMENT_TOOLS
from alfred.agents.tools.import_tools import IMPORT_TOOLS
from alfred.core.settings import settings


def build_ingest_team():
    """Build the Ingest team supervisor graph."""
    model = ChatOpenAI(
        model="gpt-4.1-mini",
        api_key=(settings.openai_api_key.get_secret_value() if settings.openai_api_key else None),
        base_url=settings.openai_base_url,
    )

    connector_agent = create_react_agent(
        model=model,
        tools=CONNECTOR_TOOLS,
        name="connector_agent",
        prompt="You query external knowledge sources (Notion, Readwise, ArXiv, RSS, etc.) to find information. Use one tool at a time.",
    )

    import_agent = create_react_agent(
        model=model,
        tools=IMPORT_TOOLS,
        name="import_agent",
        prompt="You trigger batch imports from connectors and monitor their progress. Use one tool at a time.",
    )

    enrichment_agent = create_react_agent(
        model=model,
        tools=ENRICHMENT_TOOLS,
        name="enrichment_agent",
        prompt="You enrich documents with summaries, concept extraction, classification, and zettel decomposition. Use one tool at a time.",
    )

    workflow = create_supervisor(
        agents=[connector_agent, import_agent, enrichment_agent],
        model=model,
        prompt=(
            "You are the Ingest team supervisor. Route tasks to the appropriate agent:\n"
            "- connector_agent: Live-query external sources (Notion, ArXiv, RSS, etc.)\n"
            "- import_agent: Trigger batch imports or check import status\n"
            "- enrichment_agent: Summarize, classify, or decompose documents"
        ),
    )

    return workflow.compile(name="ingest_team")
