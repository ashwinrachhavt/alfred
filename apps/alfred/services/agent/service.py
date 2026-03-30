"""Agent service — orchestrates LLM + tool calls via the master LangGraph agent.

Streams SSE events for the agent chat endpoint.
"""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator, Callable
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from sqlmodel import Session

from alfred.agents.orchestrator.graph import build_orchestrator_graph
from alfred.agents.orchestrator.registry import ToolRegistry
from alfred.agents.orchestrator.tools.knowledge import (
    make_create_zettel_tool,
    make_get_zettel_tool,
    make_search_kb_tool,
    make_update_zettel_tool,
)
from alfred.services.zettelkasten_service import ZettelkastenService

logger = logging.getLogger(__name__)


def _build_registry(db: Session) -> ToolRegistry:
    """Build a ToolRegistry with all available tools."""
    registry = ToolRegistry()
    zettel_svc = ZettelkastenService(db)

    # Phase 1: Knowledge tools (require DB session)
    registry.register(make_search_kb_tool(zettel_svc))
    registry.register(make_create_zettel_tool(zettel_svc))
    registry.register(make_get_zettel_tool(zettel_svc))
    registry.register(make_update_zettel_tool(zettel_svc))

    # Phase 1: Sub-graphs (RAG + Writer)
    try:
        from alfred.agents.orchestrator.tools.subgraphs import register_subgraphs
        register_subgraphs(registry)
    except Exception:
        logger.warning("Failed to register sub-graph tools (RAG/Writer). Continuing without them.")

    # Phase 2: Service tools (stateless, use cached dependency getters)
    try:
        from alfred.agents.orchestrator.tools.services import (
            make_autocomplete_tool,
            make_create_plan_tool,
            make_edit_text_tool,
            make_generate_diagram_tool,
            make_summarize_tool,
        )
        registry.register(make_summarize_tool())
        registry.register(make_generate_diagram_tool())
        registry.register(make_create_plan_tool())
        registry.register(make_edit_text_tool())
        registry.register(make_autocomplete_tool())
    except Exception:
        logger.warning("Failed to register Phase 2 service tools. Continuing without them.")

    return registry


def _sse_event(event: str, data: dict[str, Any]) -> str:
    """Format a single SSE event."""
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


class AgentService:
    """Orchestrates an agentic chat turn with tool calls and streaming."""

    def __init__(self, db: Session) -> None:
        self.db = db

    async def stream_turn(
        self,
        *,
        message: str,
        thread_id: int | None = None,
        history: list[dict[str, str]] | None = None,
        lens: str | None = None,
        model: str | None = None,
        note_context: dict | None = None,
        is_disconnected: Callable[[], bool] | None = None,
        intent: str | None = None,
        intent_args: dict | None = None,
        max_iterations: int = 10,
    ) -> AsyncIterator[str]:
        """Stream SSE events for one agent turn.

        Builds the orchestrator graph, invokes it, and yields SSE events
        for tokens, tool calls, artifacts, and completion.
        """
        model_name = model or "gpt-4.1-mini"

        try:
            registry = _build_registry(self.db)
            graph = build_orchestrator_graph(
                registry, model=model_name, max_iterations=max_iterations,
            )

            # Build conversation messages from history
            messages = []
            if history:
                for msg in history:
                    role = msg.get("role", "user")
                    content = msg.get("content", "")
                    if role == "user":
                        messages.append(HumanMessage(content=content))
                    else:
                        messages.append(AIMessage(content=content))

            # Add the current user message
            if message:
                messages.append(HumanMessage(content=message))
            elif intent:
                # For intent-driven actions, create a synthetic message
                messages.append(HumanMessage(content=f"[intent: {intent}] {json.dumps(intent_args or {})}"))

            # Invoke the graph
            result = graph.invoke({
                "messages": messages,
                "thread_id": str(thread_id or "ephemeral"),
                "model": model_name,
                "iteration": 0,
                "note_context": note_context,
                "intent": intent,
                "intent_args": intent_args,
            })

            # Process result messages and yield SSE events
            result_messages = result.get("messages", [])
            for msg in result_messages:
                if is_disconnected and is_disconnected():
                    return

                if isinstance(msg, AIMessage):
                    # Emit tool_start events for any tool calls
                    if getattr(msg, "tool_calls", None):
                        for tc in msg.tool_calls:
                            tc_dict = tc if isinstance(tc, dict) else {"name": tc.name, "args": tc.args}
                            yield _sse_event("tool_start", {
                                "tool": tc_dict.get("name", "unknown"),
                                "args": tc_dict.get("args", {}),
                            })
                    # Emit token event for content
                    elif msg.content:
                        yield _sse_event("token", {"content": msg.content})

                elif isinstance(msg, ToolMessage):
                    # Emit tool_end event
                    try:
                        result_data = json.loads(msg.content) if isinstance(msg.content, str) else msg.content
                    except (json.JSONDecodeError, TypeError):
                        result_data = {"raw": str(msg.content)}

                    yield _sse_event("tool_end", {
                        "tool": getattr(msg, "name", "unknown"),
                        "result_summary": str(msg.content)[:200],
                    })

                    # Emit artifact events for zettel CRUD results
                    if isinstance(result_data, dict) and result_data.get("action") in ("created", "found", "updated"):
                        yield _sse_event("artifact", {
                            "type": "zettel",
                            "action": result_data["action"],
                            "zettel": {
                                "id": result_data.get("zettel_id"),
                                "title": result_data.get("title", ""),
                                "summary": result_data.get("summary", ""),
                                "topic": result_data.get("topic", ""),
                                "tags": result_data.get("tags", []),
                            },
                        })

        except Exception as exc:
            logger.exception("Agent stream_turn failed: %s", exc)
            yield _sse_event("error", {"message": f"Agent error: {exc!s}"})

        yield _sse_event("done", {
            "thread_id": str(thread_id or ""),
        })
