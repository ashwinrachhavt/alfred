"""Redis-backed cache helpers for zettel API routes."""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from typing import Any

from fastapi import Response

from alfred.core.redis_client import get_redis_client

logger = logging.getLogger(__name__)

TOPICS_CACHE_KEY = "zettel:topics"
TAGS_CACHE_KEY = "zettel:tags"
LINK_TYPES_CACHE_KEY = "zettel:link_types"
GRAPH_EXT_CACHE_KEY = "zettel:graph:extended"
CACHE_TTL_SECONDS = 300
GRAPH_EXT_CACHE_TTL = 3600


def _resolve_redis(redis_client: Any | None = None) -> Any | None:
    return redis_client if redis_client is not None else get_redis_client()


def cache_get(key: str, *, redis_client: Any | None = None) -> Any | None:
    """Read a cached JSON value from Redis; return None on miss or decode failure."""

    redis = _resolve_redis(redis_client)
    if not redis:
        return None
    try:
        raw = redis.get(key)
        return json.loads(raw) if raw else None
    except Exception:
        logger.debug("Failed to read zettel cache key %s", key, exc_info=True)
        return None


def cache_set(
    key: str,
    value: Any,
    *,
    redis_client: Any | None = None,
    ttl_seconds: int = CACHE_TTL_SECONDS,
) -> None:
    """Best-effort write of a JSON-serializable value to Redis."""

    redis = _resolve_redis(redis_client)
    if not redis:
        return
    try:
        redis.set(key, json.dumps(value), ex=ttl_seconds)
    except Exception:
        logger.debug("Failed to write zettel cache key %s", key, exc_info=True)


def invalidate_topic_tag_cache(*, redis_client: Any | None = None) -> None:
    """Bust topics/tags cache on card mutations."""

    redis = _resolve_redis(redis_client)
    if not redis:
        return
    try:
        redis.delete(TOPICS_CACHE_KEY, TAGS_CACHE_KEY)
    except Exception:
        logger.debug("Failed to invalidate zettel topic/tag cache", exc_info=True)


def cache_delete_prefix(prefix: str, *, redis_client: Any | None = None) -> None:
    """Best-effort delete of all Redis keys matching a prefix."""

    redis = _resolve_redis(redis_client)
    if not redis:
        return
    try:
        keys = list(redis.scan_iter(f"{prefix}*"))
        if keys:
            redis.delete(*keys)
    except Exception:
        logger.debug("Failed to delete zettel cache prefix %s", prefix, exc_info=True)


def invalidate_graph_cache(
    *,
    redis_client: Any | None = None,
    invalidate_clustering: Callable[[], None] | None = None,
) -> None:
    """Bust extended graph, clustering, and link-type caches on mutation."""

    if invalidate_clustering is None:
        from alfred.services.clustering_service import ClusteringService

        invalidate_clustering = ClusteringService.invalidate_cache

    cache_delete_prefix(GRAPH_EXT_CACHE_KEY, redis_client=redis_client)
    redis = _resolve_redis(redis_client)
    if redis:
        try:
            redis.delete(LINK_TYPES_CACHE_KEY)
        except Exception:
            logger.debug("Failed to invalidate zettel link-type cache", exc_info=True)
    invalidate_clustering()


def set_cache_headers(response: Response | None, max_age: int = 30) -> None:
    if response is not None:
        response.headers["Cache-Control"] = f"private, max-age={max_age}"
