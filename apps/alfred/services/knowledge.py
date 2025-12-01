"""Knowledge service using Qdrant for vector storage and retrieval.

Provides RAG capabilities for Agno agents with document indexing and search.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any, Dict, List, Optional
from uuid import uuid4

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams

from alfred.core import agno_tracing
from alfred.core.llm_factory import get_embedding_model


@dataclass
class KnowledgeService:
    """Vector-based knowledge store using Qdrant.

    Provides document indexing and semantic search for agents.
    """

    collection_name: str = "alfred_knowledge"
    client: Optional[QdrantClient] = None
    embedder: Optional[Any] = None
    vector_size: int = 1536  # OpenAI default, adjust for other models

    def __post_init__(self) -> None:
        """Initialize Qdrant client and embedder."""
        if self.client is None:
            # Use in-memory Qdrant for prototyping
            self.client = QdrantClient(":memory:")

        if self.embedder is None:
            # Use existing embedding factory, fallback to Ollama if no OpenAI key
            from alfred.core.llm_config import settings

            try:
                self.embedder = get_embedding_model()
            except Exception:
                # Fallback to Ollama embeddings
                self.embedder = get_embedding_model(provider=settings.llm_provider.ollama)

        # Create collection if it doesn't exist
        self._ensure_collection()

    def _ensure_collection(self) -> None:
        """Create collection if it doesn't exist."""
        collections = self.client.get_collections().collections
        if not any(c.name == self.collection_name for c in collections):
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(
                    size=self.vector_size,
                    distance=Distance.COSINE,
                ),
            )

    def index_documents(
        self,
        docs: List[Dict[str, Any]],
        batch_size: int = 100,
    ) -> List[str]:
        """Index documents into the knowledge store.

        Args:
            docs: List of documents with 'id', 'text', and optional 'meta' fields
            batch_size: Number of documents to process at once

        Returns:
            List of document IDs that were indexed
        """
        indexed_ids = []

        for i in range(0, len(docs), batch_size):
            batch = docs[i : i + batch_size]
            texts = [doc["text"] for doc in batch]

            # Generate embeddings
            embeddings = self.embedder.embed_documents(texts)

            # Prepare points for Qdrant
            points = []
            for doc, embedding in zip(batch, embeddings):
                doc_id = doc.get("id") or str(uuid4())
                point = PointStruct(
                    id=self._hash_id(doc_id),
                    vector=embedding,
                    payload={
                        "doc_id": doc_id,
                        "text": doc["text"],
                        "meta": doc.get("meta", {}),
                    },
                )
                points.append(point)
                indexed_ids.append(doc_id)

            # Upload to Qdrant
            self.client.upsert(
                collection_name=self.collection_name,
                points=points,
            )

        return indexed_ids

    def search(
        self,
        query: str,
        limit: int = 5,
        score_threshold: float = 0.0,
    ) -> List[Dict[str, Any]]:
        """Search for relevant documents.

        Args:
            query: Search query text
            limit: Maximum number of results
            score_threshold: Minimum similarity score (0-1)

        Returns:
            List of matching documents with scores
        """
        # Generate query embedding
        query_embedding = self.embedder.embed_query(query)

        # Search in Qdrant
        results = self.client.search(
            collection_name=self.collection_name,
            query_vector=query_embedding,
            limit=limit,
            score_threshold=score_threshold,
        )

        # Format results
        matches = []
        for result in results:
            matches.append(
                {
                    "doc_id": result.payload["doc_id"],
                    "text": result.payload["text"],
                    "meta": result.payload.get("meta", {}),
                    "score": result.score,
                }
            )

        try:
            agno_tracing.log_knowledge_event(
                op="search",
                details={
                    "collection": self.collection_name,
                    "query": query,
                    "limit": limit,
                    "returned": len(matches),
                },
            )
        except Exception:
            pass
        return matches

    def delete_documents(self, doc_ids: List[str]) -> None:
        """Delete documents by ID."""
        point_ids = [self._hash_id(doc_id) for doc_id in doc_ids]
        self.client.delete(
            collection_name=self.collection_name,
            points_selector=point_ids,
        )

    def count(self) -> int:
        """Get total number of indexed documents."""
        info = self.client.get_collection(self.collection_name)
        return info.points_count

    @staticmethod
    def _hash_id(doc_id: str) -> int:
        """Convert string ID to integer hash for Qdrant."""
        return int(hashlib.md5(doc_id.encode()).hexdigest()[:16], 16)
