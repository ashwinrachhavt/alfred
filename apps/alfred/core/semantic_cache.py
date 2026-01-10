from __future__ import annotations

import hashlib
import json
import logging
import math
import time
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Callable, Protocol

from cachetools import TTLCache

logger = logging.getLogger(__name__)


class Embedder(Protocol):
    """Minimal protocol for embedding models used by the semantic cache."""

    def embed_query(self, text: str) -> list[float]: ...


def _stable_hash_hex(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _normalize_text(text: str) -> str:
    return " ".join((text or "").strip().split())


def _unit_normalize(vec: list[float]) -> list[float]:
    norm = math.sqrt(sum((float(x) * float(x)) for x in vec))
    if norm <= 0:
        return [0.0 for _ in vec]
    return [float(x) / norm for x in vec]


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return -1.0
    return float(sum((x * y) for x, y in zip(a, b, strict=False)))


def _signature(vec: list[float], *, bits: int, seed: str) -> str:
    """Return a stable, coarse signature for vector bucketing.

    This is intentionally lightweight and avoids requiring Redis modules (e.g., RediSearch).
    It uses the sign of selected dimensions as a locality-sensitive hash.
    """

    dim = len(vec)
    if dim <= 0 or bits <= 0:
        return ""

    packed: list[int] = []
    byte = 0
    filled = 0
    for i in range(bits):
        digest = hashlib.sha256(f"{seed}:{i}:{dim}".encode("utf-8")).digest()
        idx = int.from_bytes(digest[:4], "big") % dim
        bit = 1 if float(vec[idx]) >= 0.0 else 0
        byte = (byte << 1) | bit
        filled += 1
        if filled == 8:
            packed.append(byte)
            byte = 0
            filled = 0

    if filled:
        byte = byte << (8 - filled)
        packed.append(byte)

    return bytes(packed).hex()


@dataclass(frozen=True, slots=True)
class SemanticCacheConfig:
    """Configuration for `RedisSemanticCache`."""

    namespace: str
    ttl_seconds: int = 600
    similarity_threshold: float = 0.92
    bucket_bits: int = 64
    bucket_seeds: tuple[str, ...] = ("a", "b", "c")
    max_candidates_per_bucket: int = 25


class RedisSemanticCache:
    """Redis-backed semantic cache for small JSON-serializable values.

    The cache supports both:
    - exact lookups via a stable hash of the normalized input
    - semantic lookups by comparing embeddings of recent candidates in the same bucket(s)

    It is designed to work on plain Redis (no modules required) by using:
    - `SETEX` for value storage
    - `ZADD`/`ZREVRANGE` for bucket indices (recency-biased candidate selection)
    """

    def __init__(
        self,
        *,
        redis_client: Any,
        embedder: Embedder,
        config: SemanticCacheConfig,
        local_fallback: TTLCache[str, str] | None = None,
    ) -> None:
        self._redis = redis_client
        self._embedder = embedder
        self._config = config
        self._local = (
            local_fallback
            if local_fallback is not None
            else TTLCache(maxsize=256, ttl=max(1, int(config.ttl_seconds)))
        )

    def _item_key(self, entry_id: str) -> str:
        return f"semantic-cache:item:{self._config.namespace}:{entry_id}"

    def _exact_key(self, normalized_text: str) -> str:
        entry_id = _stable_hash_hex(f"exact:{normalized_text}")
        return self._item_key(entry_id)

    def _bucket_key(self, signature: str) -> str:
        return f"semantic-cache:bucket:{self._config.namespace}:{signature}"

    def _encode_payload(self, *, normalized_text: str, embedding: list[float], value: Any) -> str:
        payload = {
            "text": normalized_text,
            "embedding": embedding,
            "value": value,
        }
        return json.dumps(payload, separators=(",", ":"), ensure_ascii=False)

    def _decode_payload(self, raw: str) -> dict[str, Any] | None:
        try:
            payload = json.loads(raw)
        except Exception:
            return None
        if not isinstance(payload, dict):
            return None
        if "value" not in payload or "embedding" not in payload:
            return None
        return payload

    def _embed(self, normalized_text: str) -> list[float] | None:
        try:
            vec = self._embedder.embed_query(normalized_text)
        except Exception:
            logger.debug("Semantic cache: embedding failed", exc_info=True)
            return None
        if not isinstance(vec, list) or not vec:
            return None
        try:
            floats = [float(x) for x in vec]
        except Exception:
            return None
        return _unit_normalize(floats)

    def get(self, text: str) -> Any | None:
        """Return a cached value for `text` if a match is found, else None."""

        normalized = _normalize_text(text)
        if not normalized:
            return None

        # 1) Fast exact match (no embedding call).
        exact_key = self._exact_key(normalized)
        try:
            raw = self._redis.get(exact_key)
            if raw:
                payload = self._decode_payload(raw)
                if payload is not None:
                    return payload.get("value")
        except Exception:
            logger.debug("Semantic cache: exact Redis read failed", exc_info=True)

        local_raw = self._local.get(exact_key)
        if local_raw:
            payload = self._decode_payload(local_raw)
            if payload is not None:
                return payload.get("value")

        # 2) Semantic match using a small candidate set from recency buckets.
        emb = self._embed(normalized)
        if emb is None:
            return None

        best_value: Any | None = None
        best_sim = float("-inf")

        for seed in self._config.bucket_seeds:
            sig = _signature(emb, bits=self._config.bucket_bits, seed=seed)
            if not sig:
                continue
            bucket_key = self._bucket_key(sig)
            try:
                candidate_ids = self._redis.zrevrange(
                    bucket_key, 0, self._config.max_candidates_per_bucket - 1
                )
            except Exception:
                logger.debug("Semantic cache: bucket read failed", exc_info=True)
                continue

            for entry_id in candidate_ids or []:
                item_key = self._item_key(str(entry_id))
                try:
                    raw = self._redis.get(item_key)
                except Exception:
                    logger.debug("Semantic cache: candidate read failed", exc_info=True)
                    raw = None
                if not raw:
                    try:
                        self._redis.zrem(bucket_key, entry_id)
                    except Exception:
                        pass
                    continue

                payload = self._decode_payload(raw)
                if payload is None:
                    continue
                candidate_emb = payload.get("embedding")
                if not isinstance(candidate_emb, list) or len(candidate_emb) != len(emb):
                    continue
                try:
                    candidate_vec = [float(x) for x in candidate_emb]
                except Exception:
                    continue

                sim = _cosine_similarity(emb, candidate_vec)
                if sim > best_sim:
                    best_sim = sim
                    best_value = payload.get("value")

        if best_sim >= float(self._config.similarity_threshold):
            return best_value
        return None

    def _store(self, *, normalized_text: str, embedding: list[float], value: Any) -> None:
        now = time.time()
        payload = self._encode_payload(
            normalized_text=normalized_text, embedding=embedding, value=value
        )

        exact_key = self._exact_key(normalized_text)
        try:
            self._redis.setex(exact_key, int(self._config.ttl_seconds), payload)
        except Exception:
            logger.debug("Semantic cache: exact Redis write failed", exc_info=True)

        self._local[exact_key] = payload

        entry_id = _stable_hash_hex(f"semantic:{normalized_text}")
        item_key = self._item_key(entry_id)
        try:
            self._redis.setex(item_key, int(self._config.ttl_seconds), payload)
        except Exception:
            logger.debug("Semantic cache: item Redis write failed", exc_info=True)
            return

        for seed in self._config.bucket_seeds:
            sig = _signature(embedding, bits=self._config.bucket_bits, seed=seed)
            if not sig:
                continue
            bucket_key = self._bucket_key(sig)
            try:
                self._redis.zadd(bucket_key, {entry_id: float(now)})
            except Exception:
                logger.debug("Semantic cache: bucket Redis write failed", exc_info=True)

    def get_or_set(self, text: str, factory: Callable[[], Any]) -> Any:
        """Return cached value for `text` or compute+store it (best-effort).

        This avoids redundant embedding calls by reusing the same embedding for the
        semantic lookup and the subsequent store on cache misses.
        """

        normalized = _normalize_text(text)
        if not normalized:
            return factory()

        exact_key = self._exact_key(normalized)
        try:
            raw = self._redis.get(exact_key)
            if raw:
                payload = self._decode_payload(raw)
                if payload is not None:
                    return payload.get("value")
        except Exception:
            logger.debug("Semantic cache: exact Redis read failed", exc_info=True)

        local_raw = self._local.get(exact_key)
        if local_raw:
            payload = self._decode_payload(local_raw)
            if payload is not None:
                return payload.get("value")

        emb = self._embed(normalized)
        if emb is not None:
            best_value: Any | None = None
            best_sim = float("-inf")

            for seed in self._config.bucket_seeds:
                sig = _signature(emb, bits=self._config.bucket_bits, seed=seed)
                if not sig:
                    continue
                bucket_key = self._bucket_key(sig)
                try:
                    candidate_ids = self._redis.zrevrange(
                        bucket_key, 0, self._config.max_candidates_per_bucket - 1
                    )
                except Exception:
                    logger.debug("Semantic cache: bucket read failed", exc_info=True)
                    continue

                for entry_id in candidate_ids or []:
                    item_key = self._item_key(str(entry_id))
                    try:
                        raw = self._redis.get(item_key)
                    except Exception:
                        logger.debug("Semantic cache: candidate read failed", exc_info=True)
                        raw = None
                    if not raw:
                        try:
                            self._redis.zrem(bucket_key, entry_id)
                        except Exception:
                            pass
                        continue

                    payload = self._decode_payload(raw)
                    if payload is None:
                        continue
                    candidate_emb = payload.get("embedding")
                    if not isinstance(candidate_emb, list) or len(candidate_emb) != len(emb):
                        continue
                    try:
                        candidate_vec = [float(x) for x in candidate_emb]
                    except Exception:
                        continue

                    sim = _cosine_similarity(emb, candidate_vec)
                    if sim > best_sim:
                        best_sim = sim
                        best_value = payload.get("value")

            if best_sim >= float(self._config.similarity_threshold):
                return best_value

        value = factory()
        if emb is not None:
            self._store(normalized_text=normalized, embedding=emb, value=value)
        return value

    def set(self, text: str, value: Any) -> None:
        """Store `value` for `text` in the cache (best-effort)."""

        normalized = _normalize_text(text)
        if not normalized:
            return

        emb = self._embed(normalized)
        if emb is None:
            return

        self._store(normalized_text=normalized, embedding=emb, value=value)


@lru_cache(maxsize=64)
def get_semantic_cache(
    *,
    namespace: str,
    ttl_seconds: int = 600,
    similarity_threshold: float = 0.92,
) -> RedisSemanticCache | None:
    """Return a process-scoped semantic cache, or None if Redis/embeddings are unavailable."""

    try:
        from alfred.core.llm_factory import get_embedding_model
        from alfred.core.redis_client import get_redis_client
    except Exception:  # pragma: no cover - import-time dependency issues
        return None

    redis_client = get_redis_client()
    if redis_client is None:
        return None

    try:
        embedder = get_embedding_model()
    except Exception:
        return None

    config = SemanticCacheConfig(
        namespace=namespace,
        ttl_seconds=max(0, int(ttl_seconds)),
        similarity_threshold=float(similarity_threshold),
    )
    if config.ttl_seconds <= 0:
        return None
    return RedisSemanticCache(redis_client=redis_client, embedder=embedder, config=config)
