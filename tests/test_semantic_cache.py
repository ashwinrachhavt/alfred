from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

import pytest
from cachetools import TTLCache

from alfred.core.semantic_cache import RedisSemanticCache, SemanticCacheConfig


@dataclass
class _FakeEmbedder:
    """Deterministic embedder for unit tests (no network)."""

    def embed_query(self, text: str) -> list[float]:
        norm = (text or "").strip().lower()
        if "create note" in norm or "add a note" in norm:
            return [1.0, 0.0, 0.0]
        if "billing" in norm:
            return [0.0, 1.0, 0.0]
        return [0.0, 0.0, 1.0]


class _FakeRedis:
    def __init__(self, *, now: float) -> None:
        self._now = now
        self._kv: dict[str, str] = {}
        self._expires_at: dict[str, float] = {}
        self._zsets: dict[str, dict[str, float]] = {}

    def set_now(self, now: float) -> None:
        self._now = now

    def get(self, key: str) -> str | None:
        exp = self._expires_at.get(key)
        if exp is not None and self._now >= exp:
            self._kv.pop(key, None)
            self._expires_at.pop(key, None)
            return None
        return self._kv.get(key)

    def setex(self, key: str, ttl: int, value: str) -> bool:
        self._kv[key] = value
        self._expires_at[key] = self._now + max(0, int(ttl))
        return True

    def zadd(self, key: str, mapping: dict[str, float]) -> int:
        zset = self._zsets.setdefault(key, {})
        for member, score in mapping.items():
            zset[str(member)] = float(score)
        return len(mapping)

    def zrevrange(self, key: str, start: int, end: int) -> list[str]:
        zset = self._zsets.get(key, {})
        items = sorted(zset.items(), key=lambda kv: kv[1], reverse=True)
        if end < 0:
            sliced = items[start:]
        else:
            sliced = items[start : end + 1]
        return [member for member, _score in sliced]

    def zrem(self, key: str, *members: str) -> int:
        zset = self._zsets.get(key, {})
        removed = 0
        for m in members:
            if str(m) in zset:
                zset.pop(str(m), None)
                removed += 1
        return removed


def _make_cache(fake_redis: _FakeRedis) -> RedisSemanticCache:
    return RedisSemanticCache(
        redis_client=fake_redis,
        embedder=_FakeEmbedder(),
        config=SemanticCacheConfig(
            namespace="tests",
            ttl_seconds=10,
            similarity_threshold=0.9,
            bucket_bits=16,
            bucket_seeds=("a", "b"),
            max_candidates_per_bucket=10,
        ),
        local_fallback=TTLCache(maxsize=256, ttl=10, timer=lambda: fake_redis._now),
    )


def test_semantic_cache_exact_hit() -> None:
    fake_redis = _FakeRedis(now=time.time())
    cache = _make_cache(fake_redis)

    cache.set("create note", {"answer": "ok"})
    assert cache.get("create note") == {"answer": "ok"}


def test_semantic_cache_semantic_hit() -> None:
    fake_redis = _FakeRedis(now=time.time())
    cache = _make_cache(fake_redis)

    cache.set("create note", "A")
    assert cache.get("add a note") == "A"


def test_semantic_cache_ttl_expires() -> None:
    now = 1_700_000_000.0
    fake_redis = _FakeRedis(now=now)
    cache = _make_cache(fake_redis)

    cache.set("billing", "cached")
    assert cache.get("billing") == "cached"

    fake_redis.set_now(now + 15)
    assert cache.get("billing") is None


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("", None),
        ("   ", None),
        (None, None),
    ],
)
def test_semantic_cache_ignores_empty_inputs(value: Any, expected: Any) -> None:
    fake_redis = _FakeRedis(now=time.time())
    cache = _make_cache(fake_redis)
    assert cache.get(value) == expected
