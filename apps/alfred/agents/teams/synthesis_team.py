"""Synthesis team -- Research + Writing agents."""

from __future__ import annotations

from langgraph.prebuilt import create_react_agent
from langgraph_supervisor import create_supervisor

from alfred.agents.tools.research_tools import RESEARCH_TOOLS
from alfred.agents.tools.writing_tools import WRITING_TOOLS
from alfred.core.llm_factory import get_chat_model


def build_synthesis_team(*, model: str | None = None):
    """Build the Synthesis team supervisor graph."""
    team_model = get_chat_model(model=model or "gpt-4.1")

    research_agent = create_react_agent(
        model=team_model,
        tools=RESEARCH_TOOLS,
        name="research_agent",
        prompt="You conduct deep research using web search, academic papers, and the knowledge base. Synthesize findings across sources.",
    )

    writing_agent = create_react_agent(
        model=team_model,
        tools=WRITING_TOOLS,
        name="writing_agent",
        prompt="You draft zettels, create progressive summaries, explain concepts via Feynman technique, and compare perspectives.",
    )

    workflow = create_supervisor(
        agents=[research_agent, writing_agent],
        model=team_model,
        prompt=(
            "You are the Synthesis team supervisor. Route tasks to the appropriate agent:\n"
            "- research_agent: Deep research, web search, academic paper search\n"
            "- writing_agent: Draft zettels, summarize, explain, compare perspectives"
        ),
    )

    return workflow.compile(name="synthesis_team")
