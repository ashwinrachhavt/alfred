"""Backwards-compatible façade for the Agentic RAG LangGraph agent.

Graph + tool logic lives in `alfred.agents.agentic_rag` (LangGraph application structure).
This module remains to avoid touching API/service call sites across the codebase.
"""

from __future__ import annotations

from alfred.agents.agentic_rag.agent import (
    answer as answer_agentic,
)
from alfred.agents.agentic_rag.agent import (
    build_agent_graph,
    stream_answer,
)
from alfred.agents.agentic_rag.nodes import make_llm
from alfred.agents.agentic_rag.tools import (
    create_retriever_tool,
    get_context_chunks,
    make_retriever,
)

__all__ = [
    "answer_agentic",
    "build_agent_graph",
    "create_retriever_tool",
    "get_context_chunks",
    "make_llm",
    "make_retriever",
    "stream_answer",
]
