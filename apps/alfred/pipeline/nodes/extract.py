"""Extract summaries, topics, entities, and relations from document text."""

from __future__ import annotations

import logging
from typing import Any

from alfred.pipeline.state import DocumentPipelineState

logger = logging.getLogger(__name__)


def _get_extraction_service():
    from alfred.core.dependencies import get_extraction_service

    svc = get_extraction_service()
    if svc is None:
        raise RuntimeError(
            "ExtractionService is not available. Check extraction settings."
        )
    return svc


def _get_cache():
    from alfred.core.database import SessionLocal
    from alfred.pipeline.cache import PipelineStageCache

    session = SessionLocal()
    return PipelineStageCache(session=session)


def extract(state: DocumentPipelineState) -> dict[str, Any]:
    """Run extract_all + extract_graph and merge into enrichment dict."""
    content_hash = state.get("content_hash", "")
    force = state.get("force_replay", False)
    cache_hits = list(state.get("cache_hits", []))

    if not force:
        cache = _get_cache()
        cached = cache.get("extract", content_hash)
        if cached is not None:
            logger.info("Cache hit for extract:%s", content_hash)
            cache_hits.append("extract")
            return {
                "enrichment": cached,
                "cache_hits": cache_hits,
                "stage": "extract",
            }

    svc = _get_extraction_service()

    enrichment = svc.extract_all(
        cleaned_text=state["cleaned_text"],
        raw_markdown=state.get("raw_markdown"),
    )
    graph_data = svc.extract_graph(text=state["cleaned_text"])

    enrichment["relations"] = graph_data.get("relations", [])
    if graph_data.get("entities"):
        enrichment["entities"] = graph_data["entities"]

    if not force:
        cache = _get_cache()
        cache.set("extract", content_hash, enrichment)

    logger.info(
        "Extracted: %d entities, %d relations",
        len(enrichment.get("entities") or []),
        len(enrichment.get("relations") or []),
    )

    return {"enrichment": enrichment, "cache_hits": cache_hits, "stage": "extract"}
