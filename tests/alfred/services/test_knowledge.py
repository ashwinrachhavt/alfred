from __future__ import annotations

from typing import List

from alfred.services.knowledge import KnowledgeService
from qdrant_client import QdrantClient


class _FakeEmbedder:
    def __init__(self, dim: int = 8):
        self.dim = dim

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        # Deterministic small vectors
        return [[float((i + j) % 5) for j in range(self.dim)] for i, _ in enumerate(texts)]

    def embed_query(self, text: str) -> List[float]:
        return [0.1 for _ in range(self.dim)]


def test_knowledge_index_and_search():
    client = QdrantClient(":memory:")
    svc = KnowledgeService(
        collection_name="test_ks",
        client=client,
        embedder=_FakeEmbedder(dim=8),
        vector_size=8,
    )

    docs = [
        {"id": "d1", "text": "alpha beta", "meta": {"t": 1}},
        {"id": "d2", "text": "gamma delta", "meta": {"t": 2}},
    ]
    ids = svc.index_documents(docs)
    assert set(ids) == {"d1", "d2"}

    results = svc.search("alpha", limit=2)
    assert isinstance(results, list)
    assert 0 <= len(results) <= 2
