"""LangGraph StateGraph definition for the document pipeline."""

from __future__ import annotations

import logging
from typing import Any

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, StateGraph

from alfred.pipeline.nodes import (
    chunk,
    classify,
    embed,
    extract,
    load_document,
    persist,
)
from alfred.pipeline.router import resolve_next_stage
from alfred.pipeline.state import DocumentPipelineState

logger = logging.getLogger(__name__)


def _wrap_node(fn, name: str):
    """Wrap a node function with error logging."""

    def wrapper(state: DocumentPipelineState) -> dict[str, Any]:
        try:
            return fn(state)
        except Exception:
            logger.exception("Pipeline node '%s' failed", name)
            raise

    wrapper.__name__ = name
    return wrapper


def build_pipeline_graph(
    *,
    checkpointer: BaseCheckpointSaver | None = None,
) -> Any:
    """Build and compile the document pipeline StateGraph."""

    graph = StateGraph(DocumentPipelineState)

    graph.add_node("load_document", _wrap_node(load_document, "load_document"))
    graph.add_node("chunk", _wrap_node(chunk, "chunk"))
    graph.add_node("extract", _wrap_node(extract, "extract"))
    graph.add_node("classify", _wrap_node(classify, "classify"))
    graph.add_node("embed", _wrap_node(embed, "embed"))
    graph.add_node("persist", _wrap_node(persist, "persist"))

    graph.set_entry_point("load_document")

    graph.add_conditional_edges(
        "load_document",
        resolve_next_stage,
        {
            "chunk": "chunk",
            "extract": "extract",
            "classify": "classify",
            "embed": "embed",
            "persist": "persist",
        },
    )

    graph.add_edge("chunk", "extract")
    graph.add_edge("extract", "classify")
    graph.add_edge("classify", "embed")
    graph.add_edge("embed", "persist")
    graph.add_edge("persist", END)

    return graph.compile(checkpointer=checkpointer)
