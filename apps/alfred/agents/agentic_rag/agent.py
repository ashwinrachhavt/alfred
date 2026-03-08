from __future__ import annotations

from collections.abc import Iterable
from functools import lru_cache

from langchain_core.messages import HumanMessage
from langgraph.graph import END, START, StateGraph

from alfred.agents.agentic_rag.nodes import (
    generate_answer,
    generate_query_or_respond,
    grade_documents,
    rewrite_question,
    stream_final_answer,
    tools_condition_local,
)
from alfred.agents.agentic_rag.state import AgentState
from alfred.agents.agentic_rag.tools import make_tools
from alfred.agents.utils.runtime import tools_node as run_tools_node


@lru_cache(maxsize=64)
def build_agent_graph(*, k: int = 4, mode: str = "minimal"):
    workflow = StateGraph(AgentState)
    tools = make_tools(k=k)

    workflow.add_node(
        "generate_query_or_respond", lambda s: generate_query_or_respond(s, tools=tools, k=k)
    )
    workflow.add_node("tools", lambda s: run_tools_node(s, tools=tools, message_key="messages"))
    workflow.add_node("rewrite_question", rewrite_question)
    workflow.add_node("generate_answer", lambda s: generate_answer(s, mode=mode))

    workflow.add_edge(START, "generate_query_or_respond")
    workflow.add_conditional_edges(
        "generate_query_or_respond",
        tools_condition_local,
        {"tools": "tools", END: END},
    )
    workflow.add_conditional_edges("tools", grade_documents)
    workflow.add_edge("generate_answer", END)
    workflow.add_edge("rewrite_question", "generate_query_or_respond")
    return workflow.compile()


def agent():
    """LangGraph entrypoint for deployment."""

    return build_agent_graph()


def answer(question: str, *, k: int = 4, mode: str = "minimal") -> str:
    graph = build_agent_graph(k=k, mode=mode)
    final = ""
    for chunk in graph.stream({"messages": [HumanMessage(content=question)]}):
        for _node, update in chunk.items():
            try:
                msg = update["messages"][-1]
                if hasattr(msg, "content"):
                    final = msg.content
            except Exception:
                continue
    from alfred.agents.agentic_rag.nodes import enforce_first_person

    return enforce_first_person(final)


def stream_answer(question: str, *, k: int = 4, mode: str = "minimal") -> Iterable[str]:
    graph = build_agent_graph(k=k, mode=mode)
    return stream_final_answer(graph, question)
