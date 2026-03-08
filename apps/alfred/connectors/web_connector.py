from __future__ import annotations

import asyncio
import json
import logging
import os
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Literal

from alfred.core.exceptions import ConfigurationError
from alfred.core.rate_limit import web_rate_limiter
from alfred.core.settings import settings
from alfred.core.utils import clamp_int

logger = logging.getLogger(__name__)

Provider = Literal["searx", "langsearch"]


@dataclass
class SearchHit:
    title: str | None
    url: str | None
    snippet: str | None
    source: Provider
    raw: Any


@dataclass
class SearchResponse:
    provider: Provider
    query: str
    hits: list[SearchHit]
    meta: dict[str, Any] | None = None


def _env(key: str) -> str | None:
    val = os.getenv(key)
    return val.strip() if val and val.strip() else None


def _resolve_searx_host() -> str | None:
    return (
        _env("SEARXNG_HOST") or _env("SEARX_HOST") or settings.searxng_host or settings.searx_host
    )


def _normalize_list_result(items: Any, provider: Provider) -> list[SearchHit]:
    hits: list[SearchHit] = []

    def norm_one(obj: Any) -> SearchHit:
        title = None
        url = None
        snippet = None
        if isinstance(obj, dict):
            title = obj.get("title") or obj.get("name") or obj.get("page_title")
            url = obj.get("link") or obj.get("url")
            snippet = (
                obj.get("snippet")
                or obj.get("content")
                or obj.get("description")
                or (obj.get("metadata") or {}).get("summary")
            )
            md = obj.get("metadata")
            if isinstance(md, dict):
                title = title or md.get("title")
                url = url or md.get("url")
                snippet = snippet or md.get("description")
        else:
            text = str(obj)
            snippet = text[:280]
        return SearchHit(title=title, url=url, snippet=snippet, source=provider, raw=obj)

    if isinstance(items, list):
        for it in items:
            hits.append(norm_one(it))
        return hits
    if isinstance(items, str):
        try:
            parsed = json.loads(items)
            return _normalize_list_result(parsed, provider)
        except Exception:
            return [norm_one(items)]
    if isinstance(items, dict):
        for key in ("results", "data", "items", "hits"):
            v = items.get(key)
            if isinstance(v, list):
                for it in v:
                    hits.append(norm_one(it))
                break
        else:
            hits.append(norm_one(items))
    else:
        hits.append(norm_one(items))
    return hits


def _dedupe_by_url(hits: Sequence[SearchHit]) -> list[SearchHit]:
    seen: set[str] = set()
    out: list[SearchHit] = []
    for h in hits:
        key = (h.url or "").strip().lower()
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(h)
    return out


class SearxClient:
    def __init__(self, *, host: str, k: int = 10):
        from langchain_community.utilities import SearxSearchWrapper  # type: ignore

        self._host = host
        self._k_default = clamp_int(k, lo=1, hi=100)
        self._wrapper = SearxSearchWrapper(searx_host=self._host, k=self._k_default)

    def search(
        self,
        query: str,
        *,
        num_results: int,
        categories: str | None = None,
        time_range: str | None = None,
    ) -> SearchResponse:
        web_rate_limiter.wait("searx")
        res = self._wrapper.results(
            query,
            num_results=clamp_int(num_results, lo=1, hi=100),
            categories=categories,
            time_range=time_range,
        )
        hits = _normalize_list_result(res, "searx")
        meta = {"host": self._host, "k": clamp_int(num_results, lo=1, hi=100)}
        return SearchResponse(provider="searx", query=query, hits=_dedupe_by_url(hits), meta=meta)


class LangsearchClient:
    """Minimal LangSearch web-search client (HTTP JSON).

    This client is intentionally small and easy to stub for unit tests: the
    underlying HTTP implementation is held on `self._httpx` and can be replaced
    in tests without making real network calls.
    """

    def __init__(self, *, api_key: str | None = None, base_url: str | None = None) -> None:
        self._api_key = (api_key or settings.langsearch_api_key or "").strip() or None
        if not self._api_key:
            raise RuntimeError("LANGSEARCH_API_KEY is not set")
        self._base_url = (base_url or settings.langsearch_base_url).rstrip("/")
        self._httpx: Any | None = None

    @staticmethod
    def _parse_hits(payload: Any) -> list[dict[str, Any]]:
        if not isinstance(payload, dict):
            return []

        container = payload.get("data") if isinstance(payload.get("data"), dict) else payload
        web_pages = container.get("webPages") if isinstance(container, dict) else None
        values = web_pages.get("value") if isinstance(web_pages, dict) else None
        if isinstance(values, list):
            out: list[dict[str, Any]] = []
            for it in values:
                if not isinstance(it, dict):
                    continue
                out.append(
                    {
                        "title": it.get("name") or it.get("title"),
                        "url": it.get("url"),
                        "link": it.get("url"),
                        "snippet": it.get("snippet") or it.get("summary") or it.get("description"),
                        "metadata": it,
                    }
                )
            return out
        return []

    def search(
        self,
        query: str,
        *,
        count: int = 10,
        summary: bool | None = None,
        freshness: str | None = None,
    ) -> SearchResponse:
        web_rate_limiter.wait("langsearch")

        if self._httpx is None:
            try:
                import httpx  # type: ignore
            except ImportError as exc:  # pragma: no cover
                raise RuntimeError("Langsearch requires the optional dependency 'httpx'.") from exc
            self._httpx = httpx

        url = self._base_url
        headers = {"Authorization": f"Bearer {self._api_key}", "Content-Type": "application/json"}
        payload: dict[str, Any] = {"query": query, "count": clamp_int(count, lo=1, hi=10)}
        if summary is not None:
            payload["summary"] = bool(summary)
        if freshness:
            payload["freshness"] = freshness

        try:
            with self._httpx.Client(timeout=float(settings.web_langsearch_timeout_s)) as client:
                resp = client.post(url, json=payload, headers=headers)
                resp.raise_for_status()
                data = resp.json()
        except Exception as exc:
            raise RuntimeError(f"Langsearch HTTP request failed: {exc}") from exc

        normalized = self._parse_hits(data)
        hits = _normalize_list_result(normalized or data, "langsearch")
        return SearchResponse(
            provider="langsearch",
            query=query,
            hits=_dedupe_by_url(hits),
            meta={"endpoint": url, "count": payload["count"]},
        )


class WebConnector:
    """SearxNG-only web search connector.

    Alfred uses a self-hosted SearxNG instance as the single web search provider
    for predictable behavior and to avoid public-engine rate limits.
    """

    def __init__(self, *, searx_k: int = 10):
        self._searx_k_default = clamp_int(searx_k, lo=1, hi=100)
        self._client: SearxClient | None = None

        host = _resolve_searx_host()
        if not host:
            return

        try:
            self._client = SearxClient(host=host, k=self._searx_k_default)
        except Exception as exc:
            logger.warning("Searx client not available: %s", exc)
            self._client = None

    def search(
        self,
        query: str,
        *,
        num_results: int | None = None,
        categories: str | None = None,
        time_range: str | None = None,
    ) -> SearchResponse:
        if self._client is None:
            return SearchResponse(
                provider="searx", query=query, hits=[], meta={"status": "unconfigured"}
            )
        return self._client.search(
            query,
            num_results=num_results or self._searx_k_default,
            categories=categories,
            time_range=time_range,
        )

    async def asearch(self, query: str, **kwargs: Any) -> SearchResponse:
        return await asyncio.to_thread(self.search, query, **kwargs)


__all__ = [
    "ConfigurationError",
    "Provider",
    "SearchHit",
    "SearchResponse",
    "LangsearchClient",
    "SearxClient",
    "WebConnector",
    "_dedupe_by_url",
    "_env",
    "_normalize_list_result",
]
