"""State schema for the master orchestrator agent."""

from __future__ import annotations

from typing import Annotated, Any, TypedDict

from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages


class AlfredAgentState(TypedDict, total=False):
    """State for the master orchestrator ReAct loop.

    Required keys: messages, thread_id, model, iteration.
    Optional keys: note_context, intent, intent_args.
    """

    messages: Annotated[list[AnyMessage], add_messages]
    thread_id: str
    model: str
    iteration: int
    note_context: dict[str, Any] | None
    intent: str | None
    intent_args: dict[str, Any] | None
