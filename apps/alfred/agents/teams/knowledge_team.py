"""Knowledge team -- Knowledge + Connection + Learning agents.

Uses GPT-4.1-mini for all agents.
"""

from __future__ import annotations

from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent
from langgraph_supervisor import create_supervisor

from alfred.agents.tools.connection_tools import CONNECTION_TOOLS
from alfred.agents.tools.knowledge_tools import KNOWLEDGE_TOOLS
from alfred.agents.tools.learning_tools import LEARNING_TOOLS
from alfred.core.settings import settings


def build_knowledge_team():
    """Build the Knowledge team supervisor graph."""
    model = ChatOpenAI(
        model="gpt-4.1-mini",
        api_key=(settings.openai_api_key.get_secret_value() if settings.openai_api_key else None),
        base_url=settings.openai_base_url,
    )

    knowledge_agent = create_react_agent(
        model=model,
        tools=KNOWLEDGE_TOOLS,
        name="knowledge_agent",
        prompt="You search, create, retrieve, and update zettel cards and documents in the knowledge base. Use one tool at a time.",
    )

    connection_agent = create_react_agent(
        model=model,
        tools=CONNECTION_TOOLS,
        name="connection_agent",
        prompt="You discover links between zettel cards using semantic similarity and graph traversal. Use one tool at a time.",
    )

    learning_agent = create_react_agent(
        model=model,
        tools=LEARNING_TOOLS,
        name="learning_agent",
        prompt="You manage spaced repetition reviews, generate quizzes, and assess knowledge levels. Use one tool at a time.",
    )

    workflow = create_supervisor(
        agents=[knowledge_agent, connection_agent, learning_agent],
        model=model,
        prompt=(
            "You are the Knowledge team supervisor. Route tasks to the appropriate agent:\n"
            "- knowledge_agent: Search, create, read, update zettels and documents\n"
            "- connection_agent: Find similar cards, suggest links, traverse the graph\n"
            "- learning_agent: Spaced repetition, quizzes, knowledge assessment"
        ),
    )

    return workflow.compile(name="knowledge_team")
