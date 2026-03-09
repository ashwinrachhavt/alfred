"""Postgres-backed document and notes storage service.

This mirrors the Mongo DocStorageService API but persists to Postgres via SQLModel.

The implementation is split across focused mixin modules in
``alfred.services.doc_storage`` for maintainability:

- ``_notes_mixin``      — Quick-notes CRUD
- ``_ingestion_mixin``  — Document ingestion pipeline
- ``_enrichment_mixin`` — Enrichment, concept extraction, title-image generation
- ``_retrieval_mixin``  — Document retrieval, listing, text updates
- ``_semantic_map_mixin`` — Semantic map (Galaxy view) support

``DocStorageService`` inherits from all mixins and adds service-lifecycle helpers
(lazy service creation, health check).  The public API is unchanged.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Any

from cachetools import TTLCache
from sqlalchemy import func, select
from sqlmodel import Session

from alfred.core.settings import settings

# Re-export module-level helpers so any (unlikely) direct imports still work.
from alfred.services.doc_storage._chunking_helpers import (  # noqa: F401
    _build_doc_chunk_rows,
    _chunk_payloads_for_text,
)
from alfred.services.doc_storage._enrichment_mixin import EnrichmentMixin
from alfred.services.doc_storage._ingestion_mixin import IngestionMixin
from alfred.services.doc_storage._notes_mixin import NotesMixin
from alfred.services.doc_storage._retrieval_mixin import RetrievalMixin
from alfred.services.doc_storage._semantic_map_mixin import SemanticMapMixin
from alfred.services.doc_storage._session import _session_scope
from alfred.services.extraction_service import ExtractionService
from alfred.services.graph_service import GraphService
from alfred.services.llm_service import LLMService

# ---------------------------------------------------------------------------
# Constants (kept here for backward compatibility)
# ---------------------------------------------------------------------------
HSL_LIGHTNESS_MIDPOINT = 0.5
SEMANTIC_MAP_DIMENSIONS = 3
MIN_PROJECTABLE_ITEMS = 3
PAIR_ITEM_COUNT = 2
MATRIX_EXPECTED_NDIM = 2
MIN_TFIDF_FEATURES = 2


@dataclass
class DocStorageService(
    NotesMixin,
    IngestionMixin,
    EnrichmentMixin,
    RetrievalMixin,
    SemanticMapMixin,
):
    """Postgres-backed storage for notes/documents/chunks."""

    session: Session | None = None
    graph_service: Any | None = None
    extraction_service: Any | None = None
    llm_service: Any | None = None
    redis_client: Any | None = None
    semantic_map_cache_ttl_seconds: int = 600
    semantic_map_cache_lock: threading.Lock = field(default_factory=threading.Lock, repr=False)
    semantic_map_cache: TTLCache[str, dict[str, Any]] = field(
        default_factory=lambda: TTLCache(maxsize=8, ttl=600),
        repr=False,
    )

    def __post_init__(self) -> None:
        # Keep initialization side-effect free (no DB/network clients).
        # Enrichment/classification/graph connections are created lazily only
        # when an enrichment path is invoked.
        self.semantic_map_cache = TTLCache(
            maxsize=8,
            ttl=int(self.semantic_map_cache_ttl_seconds),
        )
        return

    # --------------- Lazy service creation ---------------
    def _ensure_graph_service(self) -> Any | None:
        """Lazily create the graph service if Neo4j is configured."""

        if self.graph_service is not None:
            return self.graph_service
        if not (settings.neo4j_uri and settings.neo4j_user and settings.neo4j_password):
            return None
        self.graph_service = GraphService(
            uri=settings.neo4j_uri,
            user=settings.neo4j_user,
            password=settings.neo4j_password,
        )
        return self.graph_service

    def _ensure_extraction_service(self) -> ExtractionService | None:
        """Lazily create the extraction service if enrichment is enabled."""

        if self.extraction_service is not None:
            return self.extraction_service
        needs_extraction = bool(
            settings.enable_ingest_enrichment
            or settings.enable_ingest_classification
            or self._ensure_graph_service() is not None
        )
        if not needs_extraction:
            return None
        self.extraction_service = ExtractionService(llm_service=self._ensure_llm_service())
        return self.extraction_service

    def _ensure_llm_service(self) -> LLMService:
        """Lazily create the LLM service for AI-powered features."""

        if self.llm_service is not None:
            return self.llm_service
        self.llm_service = LLMService()
        return self.llm_service

    # --------------- Health ---------------
    def ping(self) -> bool:
        try:
            with _session_scope(self.session) as s:
                s.exec(select(func.now())).first()
            return True
        except Exception as exc:  # pragma: no cover - external IO
            raise RuntimeError("Postgres not reachable") from exc

    def ensure_indexes(self) -> None:  # indexes handled via Alembic
        return


__all__ = ["DocStorageService"]
