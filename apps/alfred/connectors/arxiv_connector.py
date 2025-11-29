"""
ArXiv connector built on LangChain's community integrations.

Design goals
------------
- Thin, typed wrapper around LangChain retriever/API wrapper
- Production-minded defaults with simple overrides per call
- Clear error surfaces and input validation
- Sync and async interfaces

Notes
-----
- This connector returns `langchain_core.documents.Document` objects to integrate
  cleanly with existing RAG pipelines.
- It uses `ArxivRetriever` and applies sort options via the underlying wrapper
  when supported by the installed LangChain version.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import date, datetime
from typing import Any, Dict, List, Optional, Sequence

from langchain_community.retrievers import ArxivRetriever
from langchain_core.documents import Document

logger = logging.getLogger(__name__)


VALID_SORT_BY = {"relevance", "lastUpdatedDate", "submittedDate"}
VALID_SORT_ORDER = {"ascending", "descending"}


def _normalize_date(value: date | datetime | str) -> str:
    """Normalize date-like inputs into the YYYYMMDD format expected by arXiv queries."""
    if isinstance(value, (date, datetime)):
        return value.strftime("%Y%m%d")
    text = str(value).strip()
    digits = [c for c in text if c.isdigit()]
    if len(digits) == 8:
        return "".join(digits)
    if len(text) == 10 and text[4] in {"-", "/"} and text[7] in {"-", "/"}:
        try:
            return datetime.strptime(text, "%Y-%m-%d").strftime("%Y%m%d")
        except Exception:  # pragma: no cover - fallback to raw
            return "".join(digits)
    return "".join(digits)


def _compose_query(
    base_query: str | None,
    *,
    categories: Optional[Sequence[str]] = None,
    date_from: Optional[date | datetime | str] = None,
    date_to: Optional[date | datetime | str] = None,
) -> str:
    parts: List[str] = []
    if base_query and base_query.strip():
        parts.append(f"({base_query.strip()})")

    if categories:
        cats = [c.strip() for c in categories if c and str(c).strip()]
        if cats:
            parts.append("(" + " OR ".join(f"cat:{c}" for c in cats) + ")")

    if date_from or date_to:
        start = _normalize_date(date_from or "00010101")
        end = _normalize_date(date_to or datetime.utcnow().strftime("%Y%m%d"))
        if start and end:
            parts.append(f"submittedDate:[{start} TO {end}]")

    return " AND ".join(parts) if parts else "all:__all__"


class ArxivConnector:
    """Connector for searching arXiv via LangChain."""

    def __init__(
        self,
        *,
        load_max_docs: int = 5,
        doc_content_chars_max: int = 4000,
        load_all_available_meta: bool = False,
        sort_by: str = "relevance",
        sort_order: str = "descending",
        search_defaults: Optional[Dict[str, Any]] = None,
    ) -> None:
        self._validate_sort(sort_by, sort_order)
        self._load_max_docs = max(1, int(load_max_docs))
        self._doc_chars_max = max(256, int(doc_content_chars_max))
        self._load_all_meta = bool(load_all_available_meta)
        self._sort_by = sort_by
        self._sort_order = sort_order
        self._search_defaults = dict(search_defaults or {})

    def search(
        self,
        query: str,
        *,
        categories: Optional[Sequence[str]] = None,
        date_from: Optional[date | datetime | str] = None,
        date_to: Optional[date | datetime | str] = None,
        max_results: Optional[int] = None,
        sort_by: Optional[str] = None,
        sort_order: Optional[str] = None,
        search_kwargs: Optional[Dict[str, Any]] = None,
    ) -> List[Document]:
        effective_sort_by = sort_by or self._sort_by
        effective_sort_order = sort_order or self._sort_order
        self._validate_sort(effective_sort_by, effective_sort_order)

        q = _compose_query(query, categories=categories, date_from=date_from, date_to=date_to)
        limit = max_results or self._load_max_docs

        retriever = self._build_retriever(
            load_max_docs=limit,
            doc_content_chars_max=self._doc_chars_max,
            load_all_available_meta=self._load_all_meta,
            sort_by=effective_sort_by,
            sort_order=effective_sort_order,
            search_kwargs=search_kwargs,
        )
        return retriever.invoke(q)

    async def asearch(self, query: str, **kwargs: Any) -> List[Document]:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, lambda: self.search(query, **kwargs))

    def _build_retriever(
        self,
        *,
        load_max_docs: int,
        doc_content_chars_max: int,
        load_all_available_meta: bool,
        sort_by: str,
        sort_order: str,
        search_kwargs: Optional[Dict[str, Any]] = None,
    ) -> ArxivRetriever:
        retriever = ArxivRetriever(
            load_max_docs=load_max_docs,
            doc_content_chars_max=doc_content_chars_max,
            load_all_available_meta=load_all_available_meta,
        )

        extras: Dict[str, Any] = {"sort_by": sort_by, "sort_order": sort_order}
        extras.update(self._search_defaults)
        if search_kwargs:
            extras.update(search_kwargs)

        try:
            for attr in ("arxiv_wrapper", "api_wrapper", "client", "_arxiv_api_wrapper"):
                wrapper = getattr(retriever, attr, None)
                if wrapper is not None and hasattr(wrapper, "search_kwargs"):
                    wrapper.search_kwargs.update(extras)  # type: ignore[attr-defined]
                    break
        except Exception as exc:  # pragma: no cover - lenient configuration
            logger.debug("ArxivRetriever: could not apply search kwargs: %s", exc)

        return retriever

    @staticmethod
    def _validate_sort(sort_by: str, sort_order: str) -> None:
        sb = (sort_by or "").strip()
        so = (sort_order or "").strip()
        if sb not in VALID_SORT_BY:
            raise ValueError(
                f"Invalid sort_by '{sort_by}'. Must be one of {sorted(VALID_SORT_BY)}."
            )
        if so not in VALID_SORT_ORDER:
            raise ValueError(
                f"Invalid sort_order '{sort_order}'. Must be one of {sorted(VALID_SORT_ORDER)}."
            )


__all__ = ["ArxivConnector"]
