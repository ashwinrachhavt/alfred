"""Mixin: Semantic map (Galaxy view) support."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func
from sqlmodel import select

from alfred.models.doc_storage import DocumentRow
from alfred.services.doc_storage.semantic_map import (
    extract_embedding as _extract_embedding,
)
from alfred.services.doc_storage.semantic_map import (
    project_texts_to_3d as _project_texts_to_3d,
)
from alfred.services.doc_storage.semantic_map import (
    project_vectors_to_3d as _project_vectors_to_3d,
)
from alfred.services.doc_storage.semantic_map import (
    topic_to_color as _topic_to_color,
)
from alfred.services.doc_storage.utils import (
    best_effort_primary_topic as _best_effort_primary_topic,
)
from alfred.services.doc_storage.utils import (
    best_effort_title as _best_effort_title,
)

from ._session import _session_scope

logger = logging.getLogger(__name__)

MIN_PROJECTABLE_ITEMS = 3


class SemanticMapMixin:
    """Semantic map (Galaxy) — mixed into DocStorageService."""

    session: Any
    redis_client: Any
    semantic_map_cache: Any
    semantic_map_cache_lock: Any
    semantic_map_cache_ttl_seconds: int

    def get_semantic_map_points(
        self,
        *,
        limit: int = 5000,
        force_refresh: bool = False,
    ) -> list[dict[str, Any]]:
        """Return 3D-projected document points for the semantic map (Galaxy)."""

        limit = max(1, min(int(limit), 20_000))
        cache_key = f"documents:semantic-map:v1:limit:{limit}"

        version = self._current_semantic_map_version()
        if not force_refresh:
            cached = self._get_cached_semantic_map(cache_key, version=version)
            if cached is not None:
                return cached

        docs = self._fetch_docs_for_semantic_map(limit=limit)

        vectors: list[list[float]] = []
        embedded_docs: list[dict[str, Any]] = []
        expected_dim: int | None = None
        for d in docs:
            emb = _extract_embedding(d.get("embedding"), d.get("enrichment"))
            if not emb:
                continue
            if expected_dim is None:
                expected_dim = len(emb)
            if len(emb) != expected_dim:
                continue
            vectors.append(emb)
            embedded_docs.append(d)

        items: list[dict[str, Any]] = []

        if len(vectors) >= MIN_PROJECTABLE_ITEMS:
            coords = _project_vectors_to_3d(vectors)
            for d, pos in zip(embedded_docs, coords, strict=False):
                topic = d.get("primary_topic")
                items.append(
                    {
                        "id": d["id"],
                        "pos": pos,
                        "color": _topic_to_color(topic),
                        "label": d.get("label") or d["id"],
                        "primary_topic": topic,
                    }
                )
        else:
            texts = [f"{d.get('label') or ''} {d.get('primary_topic') or ''}".strip() for d in docs]
            coords = _project_texts_to_3d(texts)
            for d, pos in zip(docs, coords, strict=False):
                topic = d.get("primary_topic")
                items.append(
                    {
                        "id": d["id"],
                        "pos": pos,
                        "color": _topic_to_color(topic),
                        "label": d.get("label") or d["id"],
                        "primary_topic": topic,
                    }
                )

        self._set_cached_semantic_map(cache_key, version=version, items=items)
        return items

    def _current_semantic_map_version(self) -> str:
        """Return a version string for cache invalidation.

        Checks Redis first for a cached version key (set on document changes).
        Falls back to DB query only if Redis is unavailable or key is missing.
        """
        if self.redis_client is not None:
            try:
                cached = self.redis_client.get("semantic_map:version")
                if cached:
                    return cached.decode("utf-8") if isinstance(cached, bytes) else cached
            except Exception:
                pass

        with _session_scope(self.session) as s:
            ts = s.scalar(select(func.max(DocumentRow.updated_at)))
        if isinstance(ts, datetime):
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=UTC)
            version = ts.isoformat()
        else:
            version = "none"

        if self.redis_client is not None:
            try:
                self.redis_client.setex("semantic_map:version", 60, version)
            except Exception:
                pass

        return version

    def _bump_semantic_map_version(self) -> None:
        """Invalidate cached semantic map version so next request recomputes."""
        if self.redis_client is not None:
            try:
                self.redis_client.delete("semantic_map:version")
            except Exception:
                pass

    def _fetch_docs_for_semantic_map(self, *, limit: int) -> list[dict[str, Any]]:
        with _session_scope(self.session) as s:
            stmt = (
                select(
                    DocumentRow.id,
                    DocumentRow.title,
                    DocumentRow.meta,
                    DocumentRow.topics,
                    DocumentRow.enrichment,
                    DocumentRow.embedding,
                )
                .order_by(DocumentRow.updated_at.desc())
                .limit(limit)
            )
            rows = s.exec(stmt).all()

        docs: list[dict[str, Any]] = []
        for row in rows:
            meta = row.meta or {}
            label = _best_effort_title(row_title=row.title, meta=meta)
            primary_topic = _best_effort_primary_topic(row.topics, meta)
            docs.append(
                {
                    "id": str(row.id),
                    "label": label,
                    "primary_topic": primary_topic,
                    "meta": meta,
                    "topics": row.topics or {},
                    "enrichment": row.enrichment or {},
                    "embedding": row.embedding,
                }
            )
        return docs

    def _get_cached_semantic_map(
        self,
        cache_key: str,
        *,
        version: str,
    ) -> list[dict[str, Any]] | None:
        if self.redis_client is not None:
            try:
                raw = self.redis_client.get(cache_key)
                if raw:
                    payload = json.loads(raw)
                    if payload.get("version") == version and isinstance(payload.get("items"), list):
                        return payload["items"]
            except Exception:
                logger.exception("Failed reading semantic map cache from Redis")

        with self.semantic_map_cache_lock:
            cached = self.semantic_map_cache.get(cache_key)
        if cached and cached.get("version") == version and isinstance(cached.get("items"), list):
            return cached["items"]
        return None

    def _set_cached_semantic_map(
        self, cache_key: str, *, version: str, items: list[dict[str, Any]]
    ) -> None:
        payload = {"version": version, "items": items}

        if self.redis_client is not None:
            try:
                self.redis_client.setex(
                    cache_key, self.semantic_map_cache_ttl_seconds, json.dumps(payload)
                )
            except Exception:
                logger.exception("Failed writing semantic map cache to Redis")

        with self.semantic_map_cache_lock:
            self.semantic_map_cache[cache_key] = payload
