from __future__ import annotations

from typing import Any

from alfred.connectors.wikipedia_connector import WikipediaClient


def retrieve_wikipedia(
    query: str,
    lang: str = "en",
    top_k_results: int = 3,
    doc_content_chars_max: int = 4000,
    load_all_available_meta: bool = False,
    load_max_docs: int = 100,
) -> dict[str, Any]:
    client = WikipediaClient(
        lang=lang,
        top_k_results=top_k_results,
        doc_content_chars_max=doc_content_chars_max,
        load_all_available_meta=load_all_available_meta,
        load_max_docs=load_max_docs,
    )
    docs = client.search(query)
    return {
        "query": query,
        "items": [
            {
                "title": d.metadata.get("title") if d.metadata else None,
                "content": d.page_content,
                "metadata": d.metadata,
            }
            for d in docs
        ],
    }

