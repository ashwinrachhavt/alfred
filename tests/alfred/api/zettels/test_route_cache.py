from __future__ import annotations

from alfred.api.zettels.cache import (
    GRAPH_EXT_CACHE_KEY,
    LINK_TYPES_CACHE_KEY,
    TOPICS_CACHE_KEY,
    cache_get,
    cache_set,
    invalidate_graph_cache,
    invalidate_topic_tag_cache,
)


class _FakeRedis:
    def __init__(self) -> None:
        self.values: dict[str, str] = {}
        self.deleted: list[str] = []

    def get(self, key: str) -> str | None:
        return self.values.get(key)

    def set(self, key: str, value: str, ex: int) -> None:
        self.values[key] = value

    def delete(self, *keys: str) -> None:
        self.deleted.extend(keys)
        for key in keys:
            self.values.pop(key, None)

    def scan_iter(self, pattern: str):
        prefix = pattern.removesuffix("*")
        return iter([key for key in self.values if key.startswith(prefix)])


def test_cache_round_trips_json_lists() -> None:
    redis = _FakeRedis()

    cache_set(TOPICS_CACHE_KEY, ["ai", "systems"], redis_client=redis)

    assert cache_get(TOPICS_CACHE_KEY, redis_client=redis) == ["ai", "systems"]


def test_cache_get_returns_none_for_bad_json() -> None:
    redis = _FakeRedis()
    redis.values[TOPICS_CACHE_KEY] = "not-json"

    assert cache_get(TOPICS_CACHE_KEY, redis_client=redis) is None


def test_invalidate_graph_cache_deletes_extended_graph_and_link_types() -> None:
    redis = _FakeRedis()
    redis.values[f"{GRAPH_EXT_CACHE_KEY}:clusters"] = "[]"
    redis.values[f"{GRAPH_EXT_CACHE_KEY}:gaps"] = "[]"
    redis.values[LINK_TYPES_CACHE_KEY] = "[]"

    invalidate_graph_cache(redis_client=redis, invalidate_clustering=lambda: None)

    assert sorted(redis.deleted) == sorted(
        [
            f"{GRAPH_EXT_CACHE_KEY}:clusters",
            f"{GRAPH_EXT_CACHE_KEY}:gaps",
            LINK_TYPES_CACHE_KEY,
        ]
    )


def test_invalidate_topic_tag_cache_deletes_known_keys() -> None:
    redis = _FakeRedis()

    invalidate_topic_tag_cache(redis_client=redis)

    assert redis.deleted == ["zettel:topics", "zettel:tags"]
