"""Synthesizer node -- merges results from all teams into a final response."""

from __future__ import annotations

import json
import logging

from langchain_core.messages import AIMessage

from alfred.agents.state import AlfredState

logger = logging.getLogger(__name__)


def synthesizer(state: AlfredState) -> dict:
    """Merge team results into final_response."""
    messages = state.get("messages", [])
    for msg in reversed(messages):
        if isinstance(msg, AIMessage) and msg.content:
            return {"final_response": msg.content, "phase": "done"}

    all_results = (
        state.get("knowledge_results", []) + state.get("research_results", [])
        + state.get("connector_results", []) + state.get("enrichment_results", [])
    )
    if all_results:
        summary = json.dumps(all_results[:20], default=str, indent=2)
        return {"final_response": f"Here's what I found:\n\n{summary}", "phase": "done"}

    return {"final_response": "I processed your request but found no specific results.", "phase": "done"}
