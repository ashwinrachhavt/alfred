from __future__ import annotations

import json
import logging
from collections.abc import Sequence
from functools import lru_cache
from typing import Any

from langchain_core.documents import Document
from langchain_core.tools import BaseTool
from langchain_qdrant import QdrantVectorStore  # type: ignore
from qdrant_client import QdrantClient  # type: ignore

from alfred.agents.utils.web_tools import make_web_search_tool
from alfred.core.llm_factory import get_embedding_model
from alfred.core.settings import settings
from alfred.services.web_service import search_web

logger = logging.getLogger(__name__)

COLLECTION = settings.qdrant_collection or "personal_kb"
EMBED_MODEL = "text-embedding-3-small"
QDRANT_URL = settings.qdrant_url
QDRANT_API_KEY = settings.qdrant_api_key.get_secret_value() if settings.qdrant_api_key else None
ENABLE_QDRANT = bool(QDRANT_URL)


class _NullRetriever:
    """Retriever stub used when vector stores are unavailable."""

    def invoke(self, query: str) -> Sequence[Document]:  # type: ignore[override]
        return []

    async def ainvoke(self, query: str) -> Sequence[Document]:  # pragma: no cover
        return []


class _RetrieverTool(BaseTool):  # pragma: no cover - simple stringifying tool
    retriever: Any

    name: str = "retrieve_notes"
    description: str = "Retrieve relevant context snippets from the personal knowledge base."

    def _run(self, query: str) -> str:  # type: ignore[override]
        docs: Sequence[Document] = self.retriever.invoke(query)
        return "\n\n".join(getattr(d, "page_content", str(d)) for d in docs)

    async def _arun(self, query: str) -> str:  # pragma: no cover
        docs: Sequence[Document] = await self.retriever.ainvoke(query)
        return "\n\n".join(getattr(d, "page_content", str(d)) for d in docs)


@lru_cache(maxsize=1)
def _get_qdrant_client() -> QdrantClient | None:
    if not QDRANT_URL:
        return None
    try:
        client = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)
        if hasattr(client, "collection_exists"):
            exists = client.collection_exists(collection_name=COLLECTION)
            if not exists:
                raise RuntimeError(f"Qdrant collection '{COLLECTION}' not found")
        return client
    except Exception as exc:
        logger.warning("Qdrant unavailable; using no-op retriever (%s)", exc)
        return None


@lru_cache(maxsize=1)
def _get_qdrant_vector_store():
    if not ENABLE_QDRANT:
        return None
    client = _get_qdrant_client()
    if client is None:
        return None
    embed = get_embedding_model(model=EMBED_MODEL)
    try:
        return QdrantVectorStore(client=client, collection_name=COLLECTION, embedding=embed)
    except Exception as exc:
        logger.warning("Qdrant vector store unavailable; using no-op retriever (%s)", exc)
        return None


def make_retriever(k: int = 4):
    if not ENABLE_QDRANT:
        return _NullRetriever()

    vs = _get_qdrant_vector_store()
    if vs is None:
        return _NullRetriever()

    return vs.as_retriever(search_kwargs={"k": k})


def create_retriever_tool(retriever: Any, name: str, description: str) -> BaseTool:
    return _RetrieverTool(name=name, description=description, retriever=retriever)


def get_context_chunks(question: str, k: int = 4) -> list[dict]:
    retriever = make_retriever(k=k)
    docs = retriever.invoke(question)
    items = []
    for d in docs:
        items.append(
            {
                "text": d.page_content,
                "source": (d.metadata or {}).get("source"),
                "title": (d.metadata or {}).get("title"),
            }
        )
    return items


def make_tools(k: int = 4) -> list[BaseTool]:
    retriever_tool = create_retriever_tool(
        make_retriever(k=k),
        name="retrieve_notes",
        description=(
            "Search and return information from Ashwin's personal notes (vector store). "
            "Use this to answer questions about my work, projects, publications, and content."
        ),
    )
    web_tool = make_web_search_tool(search_web=search_web)
    return [retriever_tool, web_tool]


def simplify_web_results(payload: dict[str, Any], *, max_items: int = 5) -> str:
    hits = (payload or {}).get("hits") or []
    simplified = []
    for item in hits[:max_items]:
        simplified.append(
            {
                "title": item.get("title", ""),
                "url": item.get("url", ""),
                "snippet": (item.get("snippet", "") or "")[:240],
            }
        )
    return json.dumps({"results": simplified}, ensure_ascii=False)
