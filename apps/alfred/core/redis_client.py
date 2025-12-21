from __future__ import annotations

from functools import lru_cache
from typing import Any

from alfred.core.settings import settings


@lru_cache(maxsize=1)
def get_redis_client() -> Any | None:
    """Return a Redis client if the `redis` package is available.

    Note: connection is lazy; commands may still fail if Redis isn't reachable.
    """
    try:
        import redis  # type: ignore
    except Exception:
        return None

    return redis.Redis.from_url(settings.redis_url, decode_responses=True)
