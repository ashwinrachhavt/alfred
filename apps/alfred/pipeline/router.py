"""Conditional routing for replay_from and stage skipping."""

from __future__ import annotations

import logging
from typing import Any

from alfred.pipeline.state import STAGE_ORDER, STAGE_PREREQUISITES, DocumentPipelineState

logger = logging.getLogger(__name__)

_ROUTABLE_STAGES = STAGE_ORDER[1:]


def _prerequisites_met(state: dict[str, Any], stage: str) -> bool:
    """Check if all prerequisite fields for a stage are non-empty in state."""
    for field in STAGE_PREREQUISITES.get(stage, []):
        value = state.get(field)
        if not value:
            return False
    return True


def _earliest_incomplete_stage(state: dict[str, Any]) -> str:
    """Find the first stage that hasn't produced its output yet."""
    # Check if chunks exist - if not, need to chunk
    if not state.get("chunks"):
        return "chunk"
    # Check if enrichment exists - if not, need to extract
    if not state.get("enrichment"):
        return "extract"
    # Check if classification exists - if not, need to classify
    if not state.get("classification"):
        return "classify"
    # Check if embedding is done - if not, need to embed
    if not state.get("embedding_indexed"):
        return "embed"
    # Everything is done, go to persist
    return "persist"


def resolve_next_stage(state: DocumentPipelineState) -> str:
    """Determine which stage to route to after load_document.

    If replay_from is set and its prerequisites are met, jump there.
    Otherwise, fall back to the earliest incomplete stage.
    """
    # If the load step flagged errors (e.g. content is a traceback), skip to persist.
    if state.get("errors"):
        logger.warning("Errors detected after load, skipping to persist: %s", state["errors"])
        return "persist"

    target = state.get("replay_from")

    if target and target in _ROUTABLE_STAGES:
        if _prerequisites_met(state, target):
            logger.info("Routing to replay target: %s", target)
            return target
        logger.warning(
            "replay_from=%s but prerequisites not met; falling back",
            target,
        )

    return _earliest_incomplete_stage(state)
