"""Utilities for working with the LangSearch Web Search API."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence

import requests
from requests import Response, Session
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

try:
    from tinydb import TinyDB
except ImportError:  # pragma: no cover - optional dependency
    TinyDB = None  # type: ignore[assignment]

from alfred.core.config import settings

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 45
DEFAULT_COUNT = 10
STOPWORDS = {
    "the",
    "and",
    "of",
    "for",
    "to",
    "a",
    "in",
    "on",
    "with",
    "is",
    "by",
    "about",
    "from",
}


@dataclass(slots=True)
class LangSearchResult:
    query: str
    variant: str
    name: str
    url: str
    display_url: str
    snippet: str
    summary: str
    rank: int
    score: float | None = None
    raw: Dict[str, Any] = field(default_factory=dict)

    def as_record(self) -> Dict[str, Any]:
        return {
            "query": self.query,
            "variant": self.variant,
            "name": self.name,
            "url": self.url,
            "display_url": self.display_url,
            "snippet": self.snippet,
            "summary": self.summary,
            "rank": self.rank,
            "score": self.score,
            "raw": self.raw,
        }


@dataclass(slots=True)
class QueryVariant:
    query: str
    label: str
    freshness: str
    count: int
    summary: bool


class LangSearchError(RuntimeError):
    """Raised when the LangSearch API call fails."""


class LangSearchClient:
    def __init__(
        self,
        api_key: Optional[str] = None,
        *,
        base_url: Optional[str] = None,
        rerank_url: Optional[str] = None,
        db_path: Optional[str] = None,
        session: Optional[Session] = None,
    ) -> None:
        self.api_key = api_key or settings.langsearch_api_key
        if not self.api_key:
            raise ValueError(
                "LangSearch API key is not configured. Set LANGSEARCH_API_KEY or pass api_key explicitly."
            )

        self.base_url = (base_url or settings.langsearch_base_url).rstrip("/")
        self.rerank_url = (rerank_url or settings.langsearch_rerank_url or "").rstrip("/") or None

        self.session = session or self._build_session()

        storage_path = db_path or settings.langsearch_db_path
        self.db: Optional[Any]
        if storage_path and TinyDB is not None:
            path_obj = Path(storage_path)
            path_obj.parent.mkdir(parents=True, exist_ok=True)
            self.db = TinyDB(path_obj)
        else:
            if storage_path and TinyDB is None:
                logger.info("TinyDB is not installed; LangSearch results will not be persisted.")
            self.db = None

    def _build_session(self) -> Session:
        session = requests.Session()
        retry = Retry(
            total=3,
            backoff_factor=0.6,
            status_forcelist=(429, 500, 502, 503, 504),
            allowed_methods=("POST",),
        )
        adapter = HTTPAdapter(max_retries=retry)
        session.mount("https://", adapter)
        session.mount("http://", adapter)
        return session

    # Public API -----------------------------------------------------------------

    def search(
        self,
        query: str,
        *,
        count: int = DEFAULT_COUNT,
        summary: bool = True,
        freshness: Optional[str | Sequence[str]] = None,
        min_results: int = 10,
        include_rerank: bool = True,
    ) -> List[LangSearchResult]:
        """Execute multi-variant searches and return deduplicated, ranked results."""

        variants = self._build_variants(query, count=count, summary=summary, freshness=freshness)
        all_results: List[LangSearchResult] = []
        seen_urls: set[str] = set()

        for variant in variants:
            try:
                payload = self._make_payload(variant)
                data = self._post(self.base_url, payload)
            except LangSearchError as exc:  # pragma: no cover - API failure is runtime
                logger.warning("LangSearch request failed for variant '%s': %s", variant.label, exc)
                continue

            values = ((data or {}).get("data") or {}).get("webPages") or {}
            items: Iterable[Dict[str, Any]] = values.get("value") or []
            for idx, item in enumerate(items, start=1):
                url = self._clean_field(item.get("url"))
                if not url or url in seen_urls:
                    continue

                result = LangSearchResult(
                    query=query,
                    variant=variant.label,
                    name=self._clean_field(item.get("name"), "Untitled result"),
                    url=url,
                    display_url=self._clean_field(item.get("displayUrl"), url),
                    snippet=self._clean_field(item.get("snippet")),
                    summary=self._clean_field(item.get("summary")),
                    rank=idx,
                    raw=item,
                )
                all_results.append(result)
                seen_urls.add(url)

            if len(all_results) >= min_results:
                break

        if not all_results:
            return []

        self._score_results(query, all_results)

        if include_rerank and self.rerank_url:
            ordering = self._rerank(query, all_results)
            if ordering:
                all_results.sort(key=lambda r: ordering.get(r.url, 1.0), reverse=True)
            else:
                all_results.sort(key=lambda r: (r.score or 0.0), reverse=True)
        else:
            all_results.sort(key=lambda r: (r.score or 0.0), reverse=True)

        if self.db is not None:
            for record in all_results:
                self.db.insert(record.as_record())

        if min_results:
            return all_results[:min_results]
        return all_results

    def list_queries(self) -> List[str]:
        if not self.db:
            return []
        return sorted({row.get("query") for row in self.db.all() if row.get("query")})

    def clear(self) -> None:
        if self.db:
            self.db.truncate()

    # Variant construction -------------------------------------------------------

    def _build_variants(
        self,
        query: str,
        *,
        count: int,
        summary: bool,
        freshness: Optional[str | Sequence[str]],
    ) -> List[QueryVariant]:
        clean_query = query.strip()
        freshness_options: List[str]
        if freshness is None:
            freshness_options = ["noLimit", "oneYear", "oneMonth"]
        elif isinstance(freshness, str):
            freshness_options = [freshness]
        else:
            freshness_options = list(freshness)

        variants: List[QueryVariant] = []
        labels = set()

        def add_variant(q: str, label: str, fres: str) -> None:
            if (q, label, fres) in labels:
                return
            labels.add((q, label, fres))
            variants.append(
                QueryVariant(
                    query=q,
                    label=f"{label}|freshness:{fres}",
                    freshness=fres,
                    count=count,
                    summary=summary,
                )
            )

        for fres in freshness_options:
            add_variant(clean_query, "original", fres)

        trimmed = clean_query.rstrip("?!. ")
        if trimmed and trimmed != clean_query:
            for fres in freshness_options:
                add_variant(trimmed, "trimmed", fres)

        if len(clean_query.split()) > 3:
            quoted = f'"{trimmed or clean_query}"'
            for fres in freshness_options:
                add_variant(quoted, "quoted", fres)

        if len(clean_query.split()) >= 2:
            enriched = f"{trimmed or clean_query} detailed analysis"
            for fres in freshness_options[:2]:
                add_variant(enriched, "analysis", fres)

        pdf_hint = f"{trimmed or clean_query} filetype:pdf"
        add_variant(pdf_hint, "pdf", freshness_options[0])

        return variants

    # Helpers --------------------------------------------------------------------

    def _make_payload(self, variant: QueryVariant) -> Dict[str, Any]:
        payload = {
            "query": variant.query,
            "count": min(max(1, variant.count), DEFAULT_COUNT),
            "summary": variant.summary,
            "freshness": variant.freshness,
        }
        return payload

    def _post(self, url: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        try:
            response: Response = self.session.post(
                url, json=payload, headers=headers, timeout=DEFAULT_TIMEOUT
            )
        except requests.RequestException as exc:  # pragma: no cover - network failure
            raise LangSearchError(str(exc)) from exc

        if response.status_code != 200:
            raise LangSearchError(f"HTTP {response.status_code}: {response.text}")
        try:
            return response.json()
        except ValueError as exc:  # pragma: no cover - unexpected API response
            raise LangSearchError("Invalid JSON from LangSearch") from exc

    def _score_results(self, query: str, results: Sequence[LangSearchResult]) -> None:
        tokens = self._tokenize(query)
        if not tokens:
            for result in results:
                result.score = 0.0
            return

        for result in results:
            haystack = " ".join(
                filter(
                    None,
                    [result.name.lower(), result.snippet.lower(), result.summary.lower()],
                )
            )
            hits = sum(haystack.count(tok) for tok in tokens)
            bonus = 1.0 if result.variant.startswith("quoted") else 0.0
            result.score = (
                hits + bonus + max(0.0, (len(tokens) - result.variant.count("pdf")) * 0.05)
            )

    def _rerank(self, query: str, results: Sequence[LangSearchResult]) -> Dict[str, float]:
        if not self.rerank_url:
            return {}

        documents = []
        for result in results:
            text = " \n".join(filter(None, [result.name, result.summary, result.snippet]))
            documents.append({"id": result.url, "text": text})

        payload = {
            "query": query,
            "documents": documents,
            "top_k": len(documents),
        }
        try:
            data = self._post(self.rerank_url, payload)
        except LangSearchError as exc:  # pragma: no cover - rerank failures are non-fatal
            logger.info("LangSearch rerank failed: %s", exc)
            return {}

        scores: Dict[str, float] = {}
        items = data.get("data") or data.get("results") or []
        if isinstance(items, dict):
            items = items.get("results") or items.get("value") or []
        for entry in items:
            doc_id = entry.get("id") or entry.get("document_id") or entry.get("documentId")
            score = entry.get("score") or entry.get("relevance")
            if not doc_id or score is None:
                continue
            try:
                scores[str(doc_id)] = float(score)
            except (TypeError, ValueError):
                continue
        return scores

    @staticmethod
    def _tokenize(text: str) -> List[str]:
        cleaned = re.sub(r"[^a-zA-Z0-9 ]+", " ", text.lower())
        tokens = [tok for tok in cleaned.split() if tok and tok not in STOPWORDS]
        return tokens

    @staticmethod
    def _clean_field(value: Any, default: str = "") -> str:
        if value is None:
            return default
        text = str(value).strip()
        return text or default


__all__ = ["LangSearchClient", "LangSearchError", "LangSearchResult"]
