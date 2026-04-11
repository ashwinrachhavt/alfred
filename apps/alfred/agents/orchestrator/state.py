"""State schema for Alfred's orchestration graph."""

from __future__ import annotations

import operator
from typing import Annotated, Any, Literal, TypedDict

from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages

AgentKind = Literal["knowledge", "research", "connection"]
TaskMode = Literal["read", "propose_write"]
TaskStatus = Literal["queued", "running", "done", "error"]


class TaskSpec(TypedDict):
    """A single planner task routed to a specialist worker."""

    id: str
    agent: AgentKind
    objective: str
    context_refs: list[str]
    mode: TaskMode
    status: TaskStatus


class ProposedAction(TypedDict):
    """A side effect Alfred wants explicit user approval for."""

    id: str
    action: str
    reason: str
    payload: dict[str, Any]


class TaskResult(TypedDict, total=False):
    """A normalized result returned by one worker invocation."""

    task_id: str
    agent: AgentKind
    objective: str
    summary: str
    evidence: list[dict[str, Any]]
    artifacts: list[dict[str, Any]]
    related_cards: list[dict[str, Any]]
    gaps: list[dict[str, Any]]
    proposed_actions: list[ProposedAction]


class AlfredAgentState(TypedDict, total=False):
    """Top-level orchestrator state.

    Required keys: messages, thread_id, model.
    Optional keys capture planner output, worker results, and final response.
    """

    messages: Annotated[list[AnyMessage], add_messages]
    thread_id: str
    user_id: str
    model: str
    lens: str | None
    note_context: dict[str, Any] | None
    intent: str | None
    intent_args: dict[str, Any] | None
    iteration: int

    phase: str
    active_agents: list[str]
    plan: list[TaskSpec]
    current_task: TaskSpec | None
    task_results: Annotated[list[TaskResult], operator.add]
    pending_approvals: list[ProposedAction]

    artifacts: Annotated[list[dict[str, Any]], operator.add]
    related_cards: Annotated[list[dict[str, Any]], operator.add]
    gaps: Annotated[list[dict[str, Any]], operator.add]

    final_response: str | None
