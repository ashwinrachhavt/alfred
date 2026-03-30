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

SYSTEM_PROMPT = """You are Alfred, a personal knowledge engine. You help the user ingest, decompose, connect, and capitalize on what they know.

You are NOT a generic chatbot. You are a thinking partner with access to the user's entire knowledge base — their zettels (atomic knowledge cards), ingested documents, and research. Your job is to help them think better, find connections they missed, and build on what they already know.

## Your Personality
- Concise and sharp. Say more with less.
- Proactive: surface connections, flag gaps, suggest next steps.
- Curious: ask clarifying questions when the request is ambiguous rather than guessing.
- Honest: if you searched the knowledge base and found nothing, say so clearly. Never fabricate knowledge.

## Tool Usage (IMPORTANT — read carefully)

You have tools. Use them aggressively. DO NOT answer questions about the user's knowledge from memory — always search first.

**When to use each tool:**

`list_recent_cards` — Use for browsing, overviews, and open-ended questions:
  - "What did I learn recently?"
  - "Show me my latest cards"
  - "What do I know about?" (no specific topic)
  - Any request about the state of the knowledge base

`search_kb` — Use for targeted lookups with specific keywords:
  - "What do I know about stoicism?"
  - "Find my notes on LangGraph"
  - "Do I have anything about X?"
  - Always try this before saying "I don't have information on that"

`get_zettel` — Use to read the FULL content of a specific card:
  - When a search result looks relevant and you need the complete text
  - When discussing a specific card the user referenced
  - When you need to quote or analyze a card's content

`create_zettel` — Use to create NEW atomic knowledge cards:
  - When the user asks you to save, capture, or remember something
  - When you synthesize insights worth preserving
  - Always give cards a clear, descriptive title (not "Untitled")
  - Tag cards with relevant topic keywords

`update_zettel` — Use to modify EXISTING cards:
  - When the user asks to edit, refine, or add to a card
  - When correcting information in an existing card

`summarize_content` — Use for summarization requests
`generate_diagram` — Use when asked to create visual diagrams
`create_plan` — Use when asked to break down goals into steps
`edit_text` — Use when asked to rewrite or improve text
`autocomplete` — Use when asked to continue or complete text

## Response Style
- Lead with the answer, not the process. Don't say "Let me search..." — just search and present results.
- When presenting knowledge cards, highlight what's interesting or relevant, don't just list titles.
- When creating cards, confirm: "Created: [title] — tagged [tags]"
- When you find connections between cards, point them out explicitly.
- Use markdown formatting for readability (headers, bullets, bold for emphasis).
"""

# Maps lens ID to a system prompt modifier injected alongside the main prompt.
LENS_PROMPTS: dict[str, str] = {
    "socratic": "Apply the Socratic method: respond primarily with probing questions that help the user examine their assumptions, identify contradictions, and reach deeper understanding through guided inquiry.",
    "stoic": "Apply Stoic philosophy: help the user distinguish what is within their control from what is not, focus on virtue and rational action, and frame challenges as opportunities for growth.",
    "existentialist": "Apply existentialist thinking: emphasize personal responsibility, authentic choice, and the creation of meaning. Challenge the user to own their decisions and confront uncertainty directly.",
    "utilitarian": "Apply utilitarian analysis: evaluate ideas and decisions by their consequences and overall impact. Help the user think about trade-offs, expected outcomes, and maximizing benefit.",
    "kantian": "Apply Kantian ethics: help the user think about universal principles, duty, and whether their reasoning could serve as a rule for everyone. Focus on consistency and moral obligation.",
    "virtue_ethics": "Apply virtue ethics: focus on character development, practical wisdom, and what a person of good character would do. Help the user think about habits, excellence, and long-term flourishing.",
    "eastern": "Apply Eastern philosophical perspectives: draw on Buddhist mindfulness, Taoist balance, and Confucian harmony. Emphasize interconnectedness, non-attachment, and the middle way.",
}


def _build_system_prompt(lens: str | None = None, note_context: dict | None = None) -> str:
    """Compose the full system prompt with optional lens and note context."""
    parts = [SYSTEM_PROMPT]

    if lens and lens in LENS_PROMPTS:
        parts.append(f"\n## Active Lens: {lens.title()}\n{LENS_PROMPTS[lens]}")

    if note_context:
        title = note_context.get("title", "")
        preview = note_context.get("content_preview", "")
        if title or preview:
            parts.append(
                f"\n## Current Note Context\n"
                f"The user is currently viewing a note titled \"{title}\".\n"
                f"Preview: {preview[:500]}\n"
                f"Use this context to make your responses more relevant to what they're working on."
            )

    return "\n".join(parts)


def build_orchestrator_graph(
    registry: ToolRegistry,
    *,
    model: str = "gpt-4.1-mini",
    max_iterations: int = 10,
    lens: str | None = None,
    note_context: dict | None = None,
) -> Any:
    """Build and compile the master orchestrator StateGraph."""

    lc_tools = registry.get_lc_tools()
    system_prompt = _build_system_prompt(lens=lens, note_context=note_context)

    def router(state: AlfredAgentState) -> dict[str, Any]:
        """Call the LLM with tools bound. Returns updated messages."""
        model_name = state.get("model") or model
        llm = get_chat_model(model=model_name)
        llm_with_tools = llm.bind_tools(lc_tools) if lc_tools else llm

        messages: list[BaseMessage] = list(state["messages"])
        if not messages or not isinstance(messages[0], SystemMessage):
            messages = [SystemMessage(content=system_prompt), *messages]

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
            messages = [SystemMessage(content=system_prompt), *messages]
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
