"""Synthesis team -- Research + Writing agents.

Uses Alfred's configured LLM model for deep reasoning and synthesis.
"""

from __future__ import annotations

from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent
from langgraph_supervisor import create_supervisor

from alfred.agents.tools.research_tools import RESEARCH_TOOLS
from alfred.agents.tools.writing_tools import WRITING_TOOLS
from alfred.core.settings import settings


def build_synthesis_team():
    """Build the Synthesis team supervisor graph."""
    model = ChatOpenAI(
        model=settings.llm_model,
        api_key=(settings.openai_api_key.get_secret_value() if settings.openai_api_key else None),
        base_url=settings.openai_base_url,
    )

    research_agent = create_react_agent(
        model=model,
        tools=RESEARCH_TOOLS,
        name="research_agent",
        prompt="You conduct deep research using web search, academic papers, and the knowledge base. Synthesize findings across sources.",
    )

    writing_agent = create_react_agent(
        model=model,
        tools=WRITING_TOOLS,
        name="writing_agent",
        prompt="You draft zettels, create progressive summaries, explain concepts via Feynman technique, and compare perspectives.",
    )

    workflow = create_supervisor(
        agents=[research_agent, writing_agent],
        model=model,
        prompt=(
            "You are the Synthesis team supervisor. Route tasks to the appropriate agent:\n"
            "- research_agent: Deep research, web search, academic paper search\n"
            "- writing_agent: Draft zettels, summarize, explain, compare perspectives"
        ),
    )

    return workflow.compile(name="synthesis_team")
