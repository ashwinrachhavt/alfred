"""Master orchestrator agent graph.

A ReAct loop: router (LLM with tools) -> tool_executor -> router -> ... -> end.
The router decides whether to call a tool or respond directly.
"""

from __future__ import annotations

import logging
from typing import Any

from langchain_core.messages import AIMessage, BaseMessage, SystemMessage
from langgraph.graph import END, START, StateGraph

from alfred.agents.orchestrator.registry import ToolRegistry
from alfred.agents.orchestrator.state import AlfredAgentState
from alfred.agents.utils.runtime import run_tool_calls
from alfred.core.llm_factory import get_chat_model

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are Alfred, an intelligent knowledge assistant. You help the user manage their knowledge base, research topics, compose writing, and think clearly.

You have access to tools. Use them when the user's request requires searching knowledge, creating or updating cards, researching topics, or composing text. If you can answer directly from the conversation, do so without calling tools.

Be concise and helpful. When you create or update knowledge cards, confirm what you did."""


def build_orchestrator_graph(
    registry: ToolRegistry,
    *,
    model: str = "gpt-4.1-mini",
    max_iterations: int = 10,
) -> Any:
    """Build and compile the master orchestrator StateGraph."""

    lc_tools = registry.get_lc_tools()

    def router(state: AlfredAgentState) -> dict[str, Any]:
        """Call the LLM with tools bound. Returns updated messages."""
        model_name = state.get("model") or model
        llm = get_chat_model(model=model_name)
        llm_with_tools = llm.bind_tools(lc_tools) if lc_tools else llm

        messages: list[BaseMessage] = list(state["messages"])
        if not messages or not isinstance(messages[0], SystemMessage):
            messages = [SystemMessage(content=SYSTEM_PROMPT), *messages]

        response = llm_with_tools.invoke(messages)
        iteration = state.get("iteration", 0) + 1
        return {"messages": [response], "iteration": iteration}

    def tool_executor(state: AlfredAgentState) -> dict[str, Any]:
        """Execute tool calls from the last AI message."""
        messages = state["messages"]
        last = messages[-1]
        if not isinstance(last, AIMessage) or not getattr(last, "tool_calls", None):
            return {}
        tool_messages = run_tool_calls(tools=lc_tools, message=last)
        return {"messages": tool_messages}

    def force_final_response(state: AlfredAgentState) -> dict[str, Any]:
        """Force a text response when max iterations reached during tool loop."""
        model_name = state.get("model") or model
        llm = get_chat_model(model=model_name)
        # Call without tools so the LLM must respond with text
        messages: list[BaseMessage] = list(state["messages"])
        if not messages or not isinstance(messages[0], SystemMessage):
            messages = [SystemMessage(content=SYSTEM_PROMPT), *messages]
        messages.append(SystemMessage(content="You have reached the maximum number of tool calls. Please provide a final answer based on the information gathered so far."))
        response = llm.invoke(messages)
        return {"messages": [response]}

    def should_continue(state: AlfredAgentState) -> str:
        """Decide: continue to tool_executor, force final response, or end."""
        messages = state["messages"]
        last = messages[-1]
        iteration = state.get("iteration", 0)

        if iteration >= max_iterations:
            # If the last message is already a text response, end
            if isinstance(last, AIMessage) and not getattr(last, "tool_calls", None):
                return END
            # Otherwise force a final text response
            return "force_final_response"

        if isinstance(last, AIMessage) and getattr(last, "tool_calls", None):
            return "tool_executor"

        return END

    workflow = StateGraph(AlfredAgentState)
    workflow.add_node("router", router)
    workflow.add_node("tool_executor", tool_executor)
    workflow.add_node("force_final_response", force_final_response)

    workflow.add_edge(START, "router")
    workflow.add_conditional_edges("router", should_continue, {
        "tool_executor": "tool_executor",
        "force_final_response": "force_final_response",
        END: END,
    })
    workflow.add_edge("tool_executor", "router")
    workflow.add_edge("force_final_response", END)

    return workflow.compile()
