"""State schemas for the Alfred multi-agent graph.

AlfredState is the top-level shared state. Team-level states are narrower
views used by nested supervisors. Reducers on list fields use operator.add
so parallel agents can append results independently.
"""

from __future__ import annotations

import operator
from typing import Annotated, TypedDict

from langchain_core.messages import AnyMessage
from langgraph.graph import add_messages


class AlfredState(TypedDict):
    """Top-level graph state shared across all nodes."""

    messages: Annotated[list[AnyMessage], add_messages]
    user_id: str
    intent: str | None
    active_agents: list[str]
    phase: str  # "routing" | "executing" | "synthesizing" | "done"

    # Reducer-merged results from sub-agents
    knowledge_results: Annotated[list[dict], operator.add]
    research_results: Annotated[list[dict], operator.add]
    connector_results: Annotated[list[dict], operator.add]
    enrichment_results: Annotated[list[dict], operator.add]

    # Output
    final_response: str | None
    artifacts: list[dict]


class IngestTeamState(TypedDict):
    """State for the Ingest team supervisor."""

    messages: Annotated[list[AnyMessage], add_messages]
    connector_name: str | None
    import_params: dict | None
    connector_results: Annotated[list[dict], operator.add]
    enrichment_results: Annotated[list[dict], operator.add]


class KnowledgeTeamState(TypedDict):
    """State for the Knowledge team supervisor."""

    messages: Annotated[list[AnyMessage], add_messages]
    knowledge_results: Annotated[list[dict], operator.add]
    link_suggestions: list[dict]
    review_queue: list[dict]


class SynthesisTeamState(TypedDict):
    """State for the Synthesis team supervisor."""

    messages: Annotated[list[AnyMessage], add_messages]
    research_results: Annotated[list[dict], operator.add]
    final_response: str | None
    artifacts: list[dict]
