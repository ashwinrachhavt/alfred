"""SubGraphTool — wraps a compiled LangGraph sub-graph as a LangChain tool.

This adapter translates between the master agent's tool-call interface and
each sub-graph's internal state schema. Input/output mappers handle the
state translation.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from langchain_core.tools import BaseTool
from pydantic import ConfigDict, Field

logger = logging.getLogger(__name__)


class SubGraphTool(BaseTool):
    """Wrap a compiled LangGraph graph as a callable LangChain tool.

    Args:
        graph: The compiled LangGraph sub-graph.
        name: Tool name for the LLM.
        description: Tool description for the LLM.
        input_mapper: Converts tool args (dict) -> sub-graph input state (dict).
        output_mapper: Converts sub-graph output state (dict) -> tool result (str).
    """

    name: str = ""
    description: str = ""
    graph: Any = Field(exclude=True)
    input_mapper: Callable[[dict[str, Any]], dict[str, Any]] = Field(exclude=True)
    output_mapper: Callable[[dict[str, Any]], str] = Field(exclude=True)

    model_config = ConfigDict(arbitrary_types_allowed=True)

    def _run(self, **kwargs: Any) -> str:
        try:
            sub_input = self.input_mapper(kwargs)
            result = self.graph.invoke(sub_input)
            return self.output_mapper(result)
        except Exception as exc:
            logger.exception("SubGraphTool %s failed: %s", self.name, exc)
            return f"Error running {self.name}: {exc!s}"

    async def _arun(self, **kwargs: Any) -> str:
        try:
            sub_input = self.input_mapper(kwargs)
            result = await self.graph.ainvoke(sub_input)
            return self.output_mapper(result)
        except Exception as exc:
            logger.exception("SubGraphTool %s failed (async): %s", self.name, exc)
            return f"Error running {self.name}: {exc!s}"


# --- Sub-graph registration ---

from alfred.agents.agentic_rag.agent import build_agent_graph
from alfred.agents.writer.agent import build_writer_graph


def register_subgraphs(registry: Any) -> None:
    """Register RAG and Writer sub-graphs as tools in the registry."""

    # --- RAG sub-graph ---
    rag_graph = build_agent_graph()

    def rag_input_mapper(args: dict) -> dict:
        from langchain_core.messages import HumanMessage

        query = args.get("query", "")
        return {"messages": [HumanMessage(content=query)]}

    def rag_output_mapper(result: dict) -> str:
        messages = result.get("messages", [])
        if messages:
            last = messages[-1]
            return getattr(last, "content", str(last))
        return "No answer generated."

    research_tool = SubGraphTool(
        graph=rag_graph,
        name="research_topic",
        description="Research a topic using the knowledge base and web search. Returns a detailed answer. Use for open-ended questions that need retrieval.",
        input_mapper=rag_input_mapper,
        output_mapper=rag_output_mapper,
    )
    registry.register(research_tool)

    # --- Writer sub-graph ---
    writer_graph = build_writer_graph()

    def writer_input_mapper(args: dict) -> dict:
        from alfred.schemas.writing import WritingRequest

        req = WritingRequest(
            instruction=args.get("instruction", ""),
            preset=args.get("preset"),
            site_url=args.get("site_url", ""),
            context=args.get("context", ""),
        )
        return {"req": req}

    def writer_output_mapper(result: dict) -> str:
        return result.get("output", "No output generated.")

    writing_tool = SubGraphTool(
        graph=writer_graph,
        name="compose_writing",
        description="Compose polished text in a specific style/preset (linkedin, twitter, reddit, email, etc). Provide an instruction and optional preset.",
        input_mapper=writer_input_mapper,
        output_mapper=writer_output_mapper,
    )
    registry.register(writing_tool)
