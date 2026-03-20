"""Classify document into domain/subdomain taxonomy."""

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
    from alfred.core.dependencies import get_doc_storage_service
    from alfred.pipeline.cache import PipelineStageCache

    svc = get_doc_storage_service()
    session = svc._get_session()
    return PipelineStageCache(session=session)


def classify(state: DocumentPipelineState) -> dict[str, Any]:
    """Run taxonomy classification on document text."""
    content_hash = state.get("content_hash", "")
    force = state.get("force_replay", False)
    cache_hits = list(state.get("cache_hits", []))

    if not force:
        cache = _get_cache()
        cached = cache.get("classify", content_hash)
        if cached is not None:
            logger.info("Cache hit for classify:%s", content_hash)
            cache_hits.append("classify")
            return {
                "classification": cached,
                "cache_hits": cache_hits,
                "stage": "classify",
            }

    svc = _get_extraction_service()
    classification = svc.classify_taxonomy(text=state["cleaned_text"])

    if not force:
        cache = _get_cache()
        cache.set("classify", content_hash, classification)

    logger.info("Classified: domain=%s", classification.get("domain"))

    return {
        "classification": classification,
        "cache_hits": cache_hits,
        "stage": "classify",
    }
