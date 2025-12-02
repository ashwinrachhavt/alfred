from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, List

from dotenv import load_dotenv
from llama_index.core import Document, Settings, VectorStoreIndex
from llama_index.embeddings.openai import OpenAIEmbedding
from llama_index.llms.openai import OpenAI

from alfred.services.doc_storage import DocStorageService

logger = logging.getLogger(__name__)
from dotenv import load_dotenv
load_dotenv()

@dataclass
class LlamaIndexService:
    """Builds a simple in-memory VectorStoreIndex over Mongo-backed documents."""

    storage: DocStorageService
    _index: Any | None = None

    def _build_index(self, *, limit: int = 500) -> None:
        load_dotenv()
        Settings.llm = OpenAI(model="gpt-4o-mini")
        Settings.embed_model = OpenAIEmbedding(model="text-embedding-3-small")

        listing = self.storage.list_documents(skip=0, limit=limit)
        docs: List[Document] = []
        for d in listing.get("items", []):
            doc_id = d.get("id")
            if not doc_id:
                continue
            text = self.storage.get_document_text(doc_id)
            if not text:
                continue
            metadata = {
                "doc_id": doc_id,
                "title": d.get("title"),
                "source_url": d.get("source_url"),
                "canonical_url": d.get("canonical_url"),
                "topics": d.get("topics"),
            }
            docs.append(Document(text=text, metadata=metadata))

        if docs:
            self._index = VectorStoreIndex.from_documents(docs)
            logger.info("Built LlamaIndex over %d documents", len(docs))
        else:
            logger.info("No documents available to build LlamaIndex")

    def get_index(self) -> Any | None:
        if self._index is None:
            self._build_index()
        return self._index

    def query(self, question: str) -> str:
        idx = self.get_index()
        if idx is None:
            return "Index not built."
        qe = idx.as_query_engine(similarity_top_k=5)
        resp = qe.query(question)
        return str(resp)
