from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from typing import Optional

from langchain_core.embeddings import Embeddings

try:
    # Deprecated in langchain-community, but still ships and works for Redis Stack.
    from langchain_community.vectorstores.redis import Redis as RedisVectorstore
except Exception:  # pragma: no cover - optional dependency surface
    RedisVectorstore = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)


def _hash(text: str) -> str:
    return hashlib.md5(text.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class WriterCacheHit:
    output: str
    score: Optional[float] = None


class WriterSemanticCache:
    """
    Semantic cache for writer outputs using Redis Stack (RediSearch + vectors).

    This is intentionally writer-specific (stores plain strings) instead of using
    LangChain's global LLM cache, to avoid cross-service side effects.
    """

    DEFAULT_SCHEMA = {
        "content_key": "prompt",
        "text": [{"name": "prompt"}],
        "extra": [{"name": "output"}, {"name": "llm_string"}, {"name": "version"}],
    }

    def __init__(
        self,
        *,
        redis_url: str,
        embedding: Embeddings,
        version: str,
        score_threshold: float = 0.2,
        index_prefix: str = "alfred:writer_cache",
    ) -> None:
        if RedisVectorstore is None:  # pragma: no cover
            raise RuntimeError("Redis vectorstore backend is not available")
        self._cache: dict[str, RedisVectorstore] = {}
        self.redis_url = redis_url
        self.embedding = embedding
        self.score_threshold = score_threshold
        self.index_prefix = index_prefix
        self.version = version

    def _index_name(self, llm_string: str) -> str:
        return f"{self.index_prefix}:{_hash(llm_string)}"

    def _get_index(self, llm_string: str) -> RedisVectorstore:
        index_name = self._index_name(llm_string)
        if index_name in self._cache:
            return self._cache[index_name]

        try:
            vs = RedisVectorstore.from_existing_index(
                embedding=self.embedding,
                index_name=index_name,
                redis_url=self.redis_url,
                schema=dict(self.DEFAULT_SCHEMA),
            )
        except ValueError:
            vs = RedisVectorstore(
                embedding=self.embedding,
                index_name=index_name,
                redis_url=self.redis_url,
                index_schema=dict(self.DEFAULT_SCHEMA),
            )
            dim = len(self.embedding.embed_query(text="test"))
            vs._create_index_if_not_exist(dim=dim)

        self._cache[index_name] = vs
        return vs

    def lookup(self, *, prompt: str, llm_string: str) -> Optional[WriterCacheHit]:
        vs = self._get_index(llm_string)
        try:
            docs = vs.similarity_search(
                query=prompt,
                k=1,
                distance_threshold=self.score_threshold,
            )
        except Exception as exc:
            logger.warning("Writer semantic cache lookup failed: %s", exc)
            return None

        if not docs:
            return None
        doc = docs[0]
        meta = doc.metadata or {}
        if meta.get("version") != self.version:
            return None
        output = str(meta.get("output") or "")
        if not output:
            return None
        return WriterCacheHit(output=output)

    def put(self, *, prompt: str, llm_string: str, output: str) -> None:
        vs = self._get_index(llm_string)
        meta = {
            "llm_string": llm_string,
            "prompt": prompt,
            "output": output,
            "version": self.version,
        }
        try:
            vs.add_texts(texts=[prompt], metadatas=[meta])
        except Exception as exc:
            logger.warning("Writer semantic cache put failed: %s", exc)


__all__ = ["WriterCacheHit", "WriterSemanticCache"]
