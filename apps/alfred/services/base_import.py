"""Base class for knowledge import services.

Extracts the common fetch -> map -> dedup -> upsert -> stats loop shared
by all import services (Notion, Readwise, Linear, GitHub, etc.).

Concrete subclasses implement only ``fetch_items()`` and ``map_to_document()``.
Everything else (dedup via content hash, upsert, update-on-duplicate, stats
tracking, per-item error handling, logging) lives here.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any

from alfred.schemas.documents import DocumentIngest
from alfred.schemas.imports import ImportStats
from alfred.services.doc_storage_pg import DocStorageService

logger = logging.getLogger(__name__)


class BaseImportService(ABC):
    """Shared orchestration for all knowledge import services.

    Subclasses must implement:
        ``fetch_items``  -- retrieve raw items from the external source
        ``map_to_document`` -- convert one raw item into a ``DocumentIngest``

    Optionally override:
        ``item_id``  -- extract a human-readable ID for logging/stats
    """

    def __init__(self, *, doc_store: DocStorageService, source_name: str) -> None:
        self.doc_store = doc_store
        self.source_name = source_name

    # ------------------------------------------------------------------
    # Abstract interface (subclasses implement these)
    # ------------------------------------------------------------------

    @abstractmethod
    def fetch_items(self, *, since: datetime | str | None = None, **kwargs: Any) -> list[dict[str, Any]]:
        """Fetch raw items from the external source.

        Auth resolution happens inside this method -- each source handles
        credentials differently (API key, OAuth, env var).
        """
        ...

    @abstractmethod
    def map_to_document(self, item: dict[str, Any]) -> DocumentIngest:
        """Map a single source item to a ``DocumentIngest`` schema."""
        ...

    def item_id(self, item: dict[str, Any]) -> str:
        """Extract a human-readable identifier for logging. Override if needed."""
        return str(item.get("id", "unknown"))

    # ------------------------------------------------------------------
    # Orchestration (subclasses don't override this)
    # ------------------------------------------------------------------

    def run_import(self, *, since: datetime | str | None = None, **kwargs: Any) -> dict[str, Any]:
        """Fetch items, map to documents, upsert, and return stats."""
        items = self.fetch_items(since=since, **kwargs)
        stats = ImportStats()

        for item in items:
            iid = self.item_id(item)
            try:
                ingest = self.map_to_document(item)
            except Exception as exc:
                logger.warning("%s: failed to map item %s: %s", self.source_name, iid, exc)
                stats.skipped += 1
                continue

            try:
                self._upsert(ingest, iid, stats)
            except Exception as exc:
                logger.exception("%s import failed for %s", self.source_name, iid)
                stats.errors.append({"id": str(iid), "error": str(exc)})

        return stats.to_dict()

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _upsert(self, ingest: DocumentIngest, item_id: str, stats: ImportStats) -> None:
        """Ingest a document, handling dedup and update-on-duplicate."""
        res = self.doc_store.ingest_document_store_only(ingest)
        doc_id = str(res["id"])

        if res.get("duplicate"):
            try:
                self.doc_store.update_document_text(
                    doc_id,
                    title=ingest.title,
                    cleaned_text=ingest.cleaned_text,
                    raw_markdown=ingest.raw_markdown,
                    metadata_update=ingest.metadata,
                )
                stats.updated += 1
            except Exception:
                logger.debug("Skipping update for duplicate %s", doc_id)
                stats.skipped += 1
        else:
            stats.created += 1

        stats.documents.append({"id": str(item_id), "document_id": doc_id})
