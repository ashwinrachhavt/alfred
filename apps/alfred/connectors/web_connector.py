from __future__ import annotations

import asyncio
import itertools
import json
import logging
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Any, List, Literal, Optional, Sequence

from alfred.core.rate_limit import web_rate_limiter
from alfred.core.settings import settings
from alfred.core.utils import clamp_int

Provider = Literal["brave", "ddg", "exa", "tavily", "you", "searx", "langsearch"]
DEFAULT_PROVIDER_PRIORITY: List[Provider] = [
    "ddg",
    "searx",
    "brave",
    "you",
    "tavily",
    "exa",
    "langsearch",
]
Mode = Literal["auto", "multi", Provider]


@dataclass
class SearchHit:
    title: Optional[str]
    url: Optional[str]
    snippet: Optional[str]
    source: Provider
    raw: Any


@dataclass
class SearchResponse:
    provider: Provider | Literal["multi"]
    query: str
    hits: List[SearchHit]
    meta: dict[str, Any] | None = None


def _env(key: str) -> Optional[str]:
    val = os.getenv(key)
    return val.strip() if val and val.strip() else None


_PROVIDER_ENV_KEYS: dict[Provider, str] = {
    "brave": "BRAVE_SEARCH_API_KEY",
    "exa": "EXA_API_KEY",
    "tavily": "TAVILY_API_KEY",
}


def _env_configured(provider: Provider) -> bool:
    """Return True if a provider's env-based API key is present (when required).

    Some providers are intentionally re-checked at call time to support tests
    mutating env vars after `settings` has been loaded.
    """

    key = _PROVIDER_ENV_KEYS.get(provider)
    if not key:
        return True
    return _env(key) is not None


def _normalize_list_result(items: Any, provider: Provider) -> List[SearchHit]:
    hits: List[SearchHit] = []

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
            # Re-run normalization on parsed object (list/dict)
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


def _dedupe_by_url(hits: Sequence[SearchHit]) -> List[SearchHit]:
    seen: set[str] = set()
    out: List[SearchHit] = []
    for h in hits:
        key = (h.url or "").strip().lower()
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(h)
    return out


class BraveClient:
    def __init__(self, count: int = 20):
        api_key = settings.brave_search_api_key
        if not api_key:
            raise RuntimeError("BRAVE_SEARCH_API_KEY is not set")
        from langchain_community.tools import BraveSearch

        self.tool = BraveSearch.from_api_key(
            api_key=api_key, search_kwargs={"count": min(count, 20)}
        )

    def search(self, query: str, pages: int = 10) -> SearchResponse:
        pages = clamp_int(pages, lo=1, hi=10)
        all_hits: List[SearchHit] = []
        for offset in range(pages):
            web_rate_limiter.wait("brave")
            self.tool.search_wrapper.search_kwargs.update({"offset": offset})
            res = self.tool.run(query)
            all_hits.extend(_normalize_list_result(res, "brave"))
        return SearchResponse(
            provider="brave",
            query=query,
            hits=_dedupe_by_url(all_hits),
            meta={"pages": pages, "count": self.tool.search_wrapper.search_kwargs.get("count")},
        )


DEFAULT_DDG_USER_AGENT = "Mozilla/5.0 (compatible; AlfredBot/1.0; +https://github.com/alfred)"


class DDGClient:
    def __init__(
        self,
        max_results: int = 50,
        region: str = "wt-wt",
        safesearch: Literal["off", "moderate", "strict"] = "moderate",
        timelimit: Optional[str] = None,
        backend: Literal["api", "html", "lite"] = "api",
        timeout: float = 10.0,
        retries: int = 2,
        backoff_factor: float = 0.4,
    ) -> None:
        from duckduckgo_search import DDGS  # type: ignore
        from duckduckgo_search.exceptions import RatelimitException  # type: ignore

        self._DDGS = DDGS
        self._ratelimit_exc: type[Exception] = RatelimitException
        self._max_results = max_results
        self._region = region
        self._safesearch = safesearch
        self._timelimit = timelimit
        self._backend_cycle = []
        for candidate in (backend, "api", "html", "lite"):
            if candidate not in self._backend_cycle:
                self._backend_cycle.append(candidate)
        self._backend_index = 0
        self._timeout = timeout
        self._retries = max(retries, 0)
        self._backoff_factor = max(backoff_factor, 0.0)
        self._user_agent = settings.user_agent or DEFAULT_DDG_USER_AGENT
        self._client = self._make_client()

    def _make_client(self):
        return self._DDGS(timeout=self._timeout, headers={"User-Agent": self._user_agent})

    @property
    def _backend(self) -> str:
        return self._backend_cycle[self._backend_index]

    def _reset_client(self) -> None:
        try:
            if hasattr(self._client, "close"):
                self._client.close()  # type: ignore[attr-defined]
        except Exception:
            pass
        finally:
            self._client = self._make_client()

    def _advance_backend(self) -> bool:
        if self._backend_index + 1 < len(self._backend_cycle):
            self._backend_index += 1
            return True
        return False

    def _run_search(self, query: str, timelimit: Optional[str]) -> List[dict[str, Any]]:
        web_rate_limiter.wait("ddg")
        results_iter = self._client.text(
            query,
            region=self._region,
            safesearch=self._safesearch,
            timelimit=timelimit,
            backend=self._backend,
            max_results=self._max_results,
        )
        # DDGS returns a generator; slice defensively in case backend ignores max_results
        return list(itertools.islice(results_iter, self._max_results))

    def search(self, query: str, *, timelimit: Optional[str] = None) -> SearchResponse:
        attempts = self._retries + 1 + (len(self._backend_cycle) - 1)
        last_error: Exception | None = None
        effective_timelimit = timelimit or self._timelimit

        for attempt in range(attempts):
            try:
                raw_results = self._run_search(query, effective_timelimit)
                normalized_payload = []
                for item in raw_results:
                    if not isinstance(item, dict):
                        continue
                    normalized_payload.append(
                        {
                            "title": item.get("title"),
                            "url": item.get("href") or item.get("url"),
                            "link": item.get("href") or item.get("url"),
                            "snippet": item.get("body")
                            or item.get("content")
                            or item.get("description"),
                            "metadata": item,
                        }
                    )
                hits = _normalize_list_result(normalized_payload, "ddg")
                meta = {
                    "backend": self._backend,
                    "region": self._region,
                    "safesearch": self._safesearch,
                    "timelimit": effective_timelimit,
                    "results": len(hits),
                    "retries": attempt,
                    "backend_index": self._backend_index,
                    "backend_history": self._backend_cycle[: self._backend_index + 1],
                }
                return SearchResponse(
                    provider="ddg", query=query, hits=_dedupe_by_url(hits), meta=meta
                )
            except Exception as exc:
                last_error = exc
                fallback = False
                if self._ratelimit_exc and isinstance(exc, self._ratelimit_exc):
                    fallback = self._advance_backend()
                if attempt == attempts - 1 and not fallback:
                    raise
                if fallback:
                    sleep_for = self._backoff_factor * (attempt + 1)
                    if sleep_for:
                        time.sleep(sleep_for)
                    self._reset_client()
                    continue
                sleep_for = self._backoff_factor * (attempt + 1)
                if sleep_for:
                    time.sleep(sleep_for)
                self._reset_client()

        # Should be unreachable due to raise above, but keeps type-checkers happy
        raise RuntimeError(f"DuckDuckGo search failed after {attempts} attempts: {last_error}")


class ExaClient:
    def __init__(self, default_num_results: int = 100, **kwargs: Any):
        if not settings.exa_api_key:
            raise RuntimeError("EXA_API_KEY is not set")
        from langchain_exa import ExaSearchResults

        self.tool = ExaSearchResults(max_results=default_num_results, **kwargs)

    def search(
        self,
        query: str,
        num_results: int = 100,
        text_contents_options: Any = None,
        highlights: bool = True,
        **kwargs: Any,
    ) -> SearchResponse:
        web_rate_limiter.wait("exa")
        if text_contents_options is None:
            text_contents_options = {"max_characters": 3000}
        payload = {
            "query": query,
            "num_results": clamp_int(num_results, lo=1, hi=100),
            "highlights": highlights,
            "text_contents_options": text_contents_options,
        }
        payload.update(kwargs)
        res = self.tool.invoke(payload)
        hits = _normalize_list_result(res, "exa")
        return SearchResponse(provider="exa", query=query, hits=_dedupe_by_url(hits))


class TavilyClient:
    def __init__(
        self,
        max_results: int = 20,
        topic: Literal["general", "news", "finance"] = "general",
        include_answer: bool = True,
        include_raw_content: bool = True,
        **kwargs: Any,
    ):
        if not settings.tavily_api_key:
            raise RuntimeError("TAVILY_API_KEY is not set")
        from langchain_tavily import TavilySearch

        self.tool = TavilySearch(
            max_results=max_results,
            topic=topic,
            include_answer=include_answer,
            include_raw_content=include_raw_content,
            tavily_api_key=settings.tavily_api_key,
            **kwargs,
        )

    def search(self, query: str, **kwargs: Any) -> SearchResponse:
        web_rate_limiter.wait("tavily")
        res = self.tool.invoke({"query": query, **kwargs})
        hits = _normalize_list_result(res, "tavily")
        return SearchResponse(provider="tavily", query=query, hits=_dedupe_by_url(hits))


class YouClient:
    def __init__(self, num_web_results: int = 20, **kwargs: Any):
        if not settings.ydc_api_key:
            raise RuntimeError("YDC_API_KEY is not set")
        from langchain_community.tools.you import YouSearchTool
        from langchain_community.utilities.you import YouSearchAPIWrapper

        api_wrapper = YouSearchAPIWrapper(num_web_results=min(num_web_results, 19), **kwargs)
        self.tool = YouSearchTool(api_wrapper=api_wrapper)

    def search(self, query: str) -> SearchResponse:
        web_rate_limiter.wait("you")
        res = self.tool.invoke(query)
        hits = _normalize_list_result(res, "you")
        return SearchResponse(provider="you", query=query, hits=_dedupe_by_url(hits))


class SearxClient:
    def __init__(self, host: Optional[str] = None, k: int = 10):
        from langchain_community.utilities import SearxSearchWrapper  # type: ignore

        self._host = host or settings.searxng_host or settings.searx_host
        if not self._host:
            raise RuntimeError("SEARXNG_HOST (or SEARX_HOST) is not set")
        self._k_default = max(1, k)
        self._wrapper = SearxSearchWrapper(searx_host=self._host, k=self._k_default)

    def search(
        self,
        query: str,
        *,
        num_results: Optional[int] = None,
        categories: Optional[str] = None,
        time_range: Optional[str] = None,
    ) -> SearchResponse:
        web_rate_limiter.wait("searx")
        # SearxSearchWrapper returns a list of result dicts
        res = self._wrapper.results(
            query,
            num_results=(num_results or self._k_default),
            categories=categories,
            time_range=time_range,
        )
        hits = _normalize_list_result(res, "searx")
        meta = {"host": self._host, "k": num_results or self._k_default}
        return SearchResponse(provider="searx", query=query, hits=_dedupe_by_url(hits), meta=meta)


class LangsearchClient:
    def __init__(self, *, api_key: Optional[str] = None, base_url: Optional[str] = None):
        # Minimal HTTP client; enable only when properly configured
        self._api_key = api_key or settings.langsearch_api_key
        if not self._api_key:
            raise RuntimeError("LANGSEARCH_API_KEY is not set")
        self._base_url = (base_url or settings.langsearch_base_url).rstrip("/")
        try:
            import httpx  # type: ignore
        except ImportError as exc:  # pragma: no cover - httpx is a common dep
            raise ImportError(
                "Optional dependency 'httpx' not found; Langsearch client disabled."
            ) from exc
        self._httpx = httpx

    def _parse_hits(self, payload: Any) -> List[dict[str, Any]]:
        # Langsearch appears to return a Bing-like envelope under data.webPages.value
        if isinstance(payload, dict):
            container = payload.get("data") or payload
            wp = container.get("webPages") if isinstance(container, dict) else None
            if isinstance(wp, dict) and isinstance(wp.get("value"), list):
                return [
                    {
                        "title": it.get("name") or it.get("title"),
                        "url": it.get("url"),
                        "link": it.get("url"),
                        "snippet": it.get("snippet") or it.get("summary") or it.get("description"),
                        "metadata": it,
                    }
                    for it in wp["value"]
                    if isinstance(it, dict)
                ]
            # Fallbacks
            for key in ("value", "results", "items", "hits"):
                v = container.get(key) if isinstance(container, dict) else None
                if isinstance(v, list):
                    return [
                        {
                            "title": getattr(it, "name", None)
                            if not isinstance(it, dict)
                            else it.get("name") or it.get("title"),
                            "url": getattr(it, "url", None)
                            if not isinstance(it, dict)
                            else it.get("url") or it.get("link"),
                            "link": getattr(it, "url", None)
                            if not isinstance(it, dict)
                            else it.get("url") or it.get("link"),
                            "snippet": getattr(it, "snippet", None)
                            if not isinstance(it, dict)
                            else it.get("snippet") or it.get("summary") or it.get("description"),
                            "metadata": it,
                        }
                        for it in v
                    ]
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
        # LangSearch Web Search API endpoint is the base URL itself, e.g.
        # https://api.langsearch.com/v1/web-search
        url = self._base_url
        headers = {"Authorization": f"Bearer {self._api_key}", "Content-Type": "application/json"}
        payload: dict[str, Any] = {"query": query, "count": clamp_int(count, lo=1, hi=10)}
        if summary is not None:
            payload["summary"] = bool(summary)
        if freshness:
            payload["freshness"] = freshness
        try:
            with self._httpx.Client(timeout=10.0) as client:
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
    def __init__(
        self,
        mode: Mode = "auto",
        *,
        brave_count: int = 20,
        brave_pages: int = 10,
        ddg_max_results: int = 50,
        exa_num_results: int = 100,
        tavily_max_results: int = 20,
        tavily_topic: Literal["general", "news", "finance"] = "general",
        you_num_results: int = 20,
        searx_k: int = 10,
    ):
        self.mode = mode
        self._init_clients(
            brave_count,
            ddg_max_results,
            exa_num_results,
            tavily_max_results,
            tavily_topic,
            you_num_results,
            searx_k,
        )
        self._brave_pages_default = brave_pages

    def _init_clients(
        self,
        brave_count: int,
        ddg_max_results: int,
        exa_num_results: int,
        tavily_max_results: int,
        tavily_topic: str,
        you_num_results: int,
        searx_k: int,
    ) -> None:
        self.clients: dict[Provider, Any] = {}
        if settings.exa_api_key:
            try:
                self.clients["exa"] = ExaClient(default_num_results=exa_num_results)
            except ImportError as exc:
                logging.warning("Exa client disabled: %s", exc)
        if settings.tavily_api_key:
            try:
                self.clients["tavily"] = TavilyClient(
                    max_results=tavily_max_results, topic=tavily_topic
                )
            except ImportError as exc:
                logging.warning("Tavily client disabled: %s", exc)
        if settings.brave_search_api_key:
            self.clients["brave"] = BraveClient(count=brave_count)
        if settings.ydc_api_key:
            try:
                self.clients["you"] = YouClient(num_web_results=you_num_results)
            except ImportError as exc:
                logging.warning("You.com client disabled: %s", exc)
        try:
            self.clients["ddg"] = DDGClient(max_results=ddg_max_results)
        except ImportError as exc:
            logging.warning("DDG client disabled: %s", exc)
        # SearxNG client (enabled when SEARXNG_HOST/SEARX_HOST is set and langchain-community is present)
        try:
            searx_host = (
                _env("SEARXNG_HOST")
                or _env("SEARX_HOST")
                or settings.searxng_host
                or settings.searx_host
            )
            if searx_host:
                self.clients["searx"] = SearxClient(host=searx_host, k=searx_k)
        except Exception as exc:
            logging.warning("Searx client not available: %s", exc)
        # Langsearch client (enabled when LANGSEARCH_API_KEY present)
        try:
            langsearch_key = _env("LANGSEARCH_API_KEY") or settings.langsearch_api_key
            if langsearch_key:
                base_url = _env("LANGSEARCH_BASE_URL") or settings.langsearch_base_url
                self.clients["langsearch"] = LangsearchClient(
                    api_key=langsearch_key,
                    base_url=base_url,
                )
        except Exception as exc:
            logging.warning(f"Langsearch client not available: {exc}")

    def _resolve_auto(self) -> Provider:
        for p in DEFAULT_PROVIDER_PRIORITY:
            if p in self.clients:
                return p  # type: ignore
        return "ddg"

    def _collect_enabled(self) -> List[Provider]:
        return [p for p in DEFAULT_PROVIDER_PRIORITY if p in self.clients]

    def _search_multi(self, query: str, **kwargs: Any) -> SearchResponse:
        providers = self._collect_enabled()

        def call(p: Provider):
            c = self.clients[p]
            if p == "brave":
                # In multi-provider mode, pagination can explode request counts and trigger 429s.
                return c.search(query, pages=1)
            if p == "exa":
                return c.search(query, num_results=kwargs.get("num_results", 100))
            return c.search(query)

        # Run provider calls concurrently using a thread pool to avoid
        # interacting with any already-running asyncio event loop (e.g. FastAPI).
        results: List[SearchResponse] = []
        errors: dict[str, Any] = {}
        if not providers:
            return SearchResponse(provider="multi", query=query, hits=[], meta={"providers": []})
        # Keep concurrency low to avoid bursting across providers.
        max_workers = min(2, len(providers)) or 1
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_map = {executor.submit(call, p): p for p in providers}
            for future in as_completed(future_map):
                prov = future_map[future]
                try:
                    res = future.result()
                    if isinstance(res, SearchResponse):
                        results.append(res)
                except Exception as exc:  # pragma: no cover - network/provider failures
                    logging.warning("Web provider '%s' failed: %s", prov, exc)
                    errors[prov] = str(exc)
        merged = _dedupe_by_url([h for r in results for h in r.hits])
        return SearchResponse(
            provider="multi",
            query=query,
            hits=merged,
            meta={
                "providers": providers,
                "sizes": {r.provider: len(r.hits) for r in results},
                "errors": errors or None,
            },
        )

    def search(self, query: str, *, pages: Optional[int] = None, **kwargs: Any) -> SearchResponse:
        if self.mode == "multi":
            return self._search_multi(query, **kwargs)
        provider: Provider = self._resolve_auto() if self.mode == "auto" else self.mode

        # Re-check env-based configuration at call time to handle tests that mutate env after settings load.
        if not _env_configured(provider):
            logging.warning(
                "Provider '%s' not configured. Returning empty fallback response.", provider
            )
            return SearchResponse(
                provider=provider, query=query, hits=[], meta={"status": "unconfigured"}
            )

        client = self.clients.get(provider)
        if not client:
            if provider not in self.clients:
                logging.warning(
                    f"Provider '{provider}' not configured. Returning empty fallback response."
                )
                return SearchResponse(
                    provider=provider, query=query, hits=[], meta={"status": "unconfigured"}
                )
            raise RuntimeError(f"Provider '{provider}' is not configured")
        if provider == "brave":
            return client.search(query, pages=pages or self._brave_pages_default)
        if provider == "exa":
            num = kwargs.pop("num_results", 100)
            return client.search(query, num_results=num, **kwargs)
        if provider == "searx":
            # Map common kwargs where applicable
            num = kwargs.pop("num_results", None)
            return client.search(query, num_results=num, **kwargs)
        if provider == "langsearch":
            count = kwargs.pop("count", 20)
            return client.search(query, count=count)
        return client.search(query, **kwargs)

    async def asearch(self, query: str, **kwargs: Any) -> SearchResponse:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, lambda: self.search(query, **kwargs))
