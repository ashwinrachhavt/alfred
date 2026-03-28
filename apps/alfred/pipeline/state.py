"""Pipeline state schema and stage metadata."""

from __future__ import annotations

from typing import Any, TypedDict


class DocumentPipelineState(TypedDict, total=False):
    # Identity
    doc_id: str
    user_id: str

    # Content (loaded from DB, flows through all stages)
    title: str
    cleaned_text: str
    raw_markdown: str
    content_hash: str  # mapped from DocumentRow.hash

    # Stage outputs (accumulated as pipeline progresses)
    chunks: list[dict[str, Any]]       # DocumentIngestChunk.model_dump() per chunk
    enrichment: dict[str, Any]         # from extract node
    classification: dict[str, Any]     # from classify node
    embedding_indexed: bool            # from embed node

    # Pipeline metadata
    stage: str                         # current stage name
    errors: list[dict[str, Any]]       # [{stage, error, timestamp}]
    cache_hits: list[str]              # stages that returned cached results
    force_replay: bool                 # bypass cache for all stages
    replay_from: str | None            # skip stages before this one


# Ordered list of backbone pipeline stages
STAGE_ORDER: list[str] = [
    "load_document",
    "chunk",
    "extract",
    "classify",
    "embed",
    "persist",
]

# For each stage, the state fields that must be non-empty for it to run.
# Used by the replay router to validate replay_from targets.
STAGE_PREREQUISITES: dict[str, list[str]] = {
    "load_document": [],
    "chunk": ["cleaned_text"],
    "extract": ["cleaned_text"],
    "classify": ["cleaned_text"],
    "embed": ["chunks"],
    "persist": ["chunks", "enrichment"],
}
