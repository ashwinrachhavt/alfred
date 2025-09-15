from __future__ import annotations

import asyncio
from typing import Any

from langchain_community.retrievers import WikipediaRetriever
from langchain_core.documents import Document


class WikipediaClient:
    """Thin wrapper around LangChain WikipediaRetriever."""

    def __init__(
        self,
        lang: str = "en",
        top_k_results: int = 3,
        doc_content_chars_max: int = 4000,
        load_all_available_meta: bool = False,
        load_max_docs: int = 100,
        **kwargs: Any,
    ) -> None:
        self.retriever = WikipediaRetriever(
            lang=lang,
            top_k_results=top_k_results,
            doc_content_chars_max=doc_content_chars_max,
            load_all_available_meta=load_all_available_meta,
            load_max_docs=load_max_docs,
            **kwargs,
        )

    def search(self, query: str) -> list[Document]:
        return self.retriever.invoke(query)

    async def asearch(self, query: str) -> list[Document]:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, lambda: self.search(query))

