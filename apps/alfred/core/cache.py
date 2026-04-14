"""Reusable Redis cache utility.

Best-effort semantics: cache failures never raise, never block.
"""
from __future__ import annotations

import json
import logging
from typing import Any

from alfred.core.redis_client import get_redis_client

_log = logging.getLogger(__name__)


def cache_get(key: str) -> Any | None:
    """Read a cached JSON value. Returns None on miss or error."""
    redis = get_redis_client()
    if not redis:
        return None
    try:
        raw = redis.get(key)
        return json.loads(raw) if raw else None
    except Exception:
        return None


def cache_set(key: str, value: Any, *, ttl: int = 60) -> None:
    """Best-effort write with TTL in seconds."""
    redis = get_redis_client()
    if not redis:
        return
    try:
        redis.set(key, json.dumps(value), ex=ttl)
    except Exception:
        pass


def cache_invalidate(prefix: str) -> None:
    """Best-effort delete all keys matching prefix."""
    redis = get_redis_client()
    if not redis:
        return
    try:
        for key in redis.scan_iter(f"{prefix}*"):
            redis.delete(key)
    except Exception:
        pass
