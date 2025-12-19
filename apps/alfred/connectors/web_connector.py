from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor, as_completed
import itertools
import json
import logging
import os
import time
from dataclasses import dataclass
from typing import Any, List, Literal, Optional, Sequence

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
        api_key = _env("BRAVE_SEARCH_API_KEY")
        if not api_key:
            raise RuntimeError("BRAVE_SEARCH_API_KEY is not set")
        from langchain_community.tools import BraveSearch

        self.tool = BraveSearch.from_api_key(
            api_key=api_key, search_kwargs={"count": min(count, 20)}
        )

    def search(self, query: str, pages: int = 10) -> SearchResponse:
        pages = max(1, min(pages, 10))
        all_hits: List[SearchHit] = []
        for offset in range(pages):
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
        self._user_agent = os.getenv("USER_AGENT", DEFAULT_DDG_USER_AGENT)
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
        if not _env("EXA_API_KEY"):
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
        if text_contents_options is None:
            text_contents_options = {"max_characters": 3000}
        payload = {
            "query": query,
            "num_results": max(1, min(num_results, 100)),
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
        if not _env("TAVILY_API_KEY"):
            raise RuntimeError("TAVILY_API_KEY is not set")
        from langchain_tavily import TavilySearch

        self.tool = TavilySearch(
            max_results=max_results,
            topic=topic,
            include_answer=include_answer,
            include_raw_content=include_raw_content,
            **kwargs,
        )

    def search(self, query: str, **kwargs: Any) -> SearchResponse:
        res = self.tool.invoke({"query": query, **kwargs})
        hits = _normalize_list_result(res, "tavily")
        return SearchResponse(provider="tavily", query=query, hits=_dedupe_by_url(hits))


class YouClient:
    def __init__(self, num_web_results: int = 20, **kwargs: Any):
        if not _env("YDC_API_KEY"):
            raise RuntimeError("YDC_API_KEY is not set")
        from langchain_community.tools.you import YouSearchTool
        from langchain_community.utilities.you import YouSearchAPIWrapper

        api_wrapper = YouSearchAPIWrapper(num_web_results=min(num_web_results, 19), **kwargs)
        self.tool = YouSearchTool(api_wrapper=api_wrapper)

    def search(self, query: str) -> SearchResponse:
        res = self.tool.invoke(query)
        hits = _normalize_list_result(res, "you")
        return SearchResponse(provider="you", query=query, hits=_dedupe_by_url(hits))


class SearxClient:
    def __init__(self, host: Optional[str] = None, k: int = 10):
        from langchain_community.utilities import SearxSearchWrapper  # type: ignore

        self._host = host or _env("SEARXNG_HOST") or _env("SEARX_HOST")
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
        self._api_key = api_key or _env("LANGSEARCH_API_KEY")
        if not self._api_key:
            raise RuntimeError("LANGSEARCH_API_KEY is not set")
        self._base_url = (
            base_url or _env("LANGSEARCH_API_URL") or "https://api.langsearch.com/v1"
        ).rstrip("/")
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

    def search(self, query: str, *, count: int = 20) -> SearchResponse:
        # Best-effort API call shape; users can override base_url via env if needed
        url = f"{self._base_url}/search"
        headers = {"Authorization": f"Bearer {self._api_key}", "Content-Type": "application/json"}
        payload = {"q": query, "count": max(1, min(count, 50))}
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
        if _env("EXA_API_KEY"):
            try:
                self.clients["exa"] = ExaClient(default_num_results=exa_num_results)
            except ImportError as exc:
                logging.warning("Exa client disabled: %s", exc)
        if _env("TAVILY_API_KEY"):
            try:
                self.clients["tavily"] = TavilyClient(
                    max_results=tavily_max_results, topic=tavily_topic
                )
            except ImportError as exc:
                logging.warning("Tavily client disabled: %s", exc)
        if _env("BRAVE_SEARCH_API_KEY"):
            self.clients["brave"] = BraveClient(count=brave_count)
        if _env("YDC_API_KEY"):
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
            if _env("SEARXNG_HOST") or _env("SEARX_HOST"):
                self.clients["searx"] = SearxClient(k=searx_k)
        except Exception as exc:
            logging.warning("Searx client not available: %s", exc)
        # Langsearch client (enabled when LANGSEARCH_API_KEY present)
        try:
            if _env("LANGSEARCH_API_KEY"):
                self.clients["langsearch"] = LangsearchClient()
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
                return c.search(query, pages=self._brave_pages_default)
            if p == "exa":
                return c.search(query, num_results=kwargs.get("num_results", 100))
            return c.search(query)

        # Run provider calls concurrently using a thread pool to avoid
        # interacting with any already-running asyncio event loop (e.g. FastAPI).
        results: List[SearchResponse] = []
        errors: dict[str, Any] = {}
        if not providers:
            return SearchResponse(provider="multi", query=query, hits=[], meta={"providers": []})
        max_workers = min(8, len(providers)) or 1
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


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="WebConnector quick test")
    parser.add_argument("query", type=str)
    parser.add_argument(
        "--mode",
        choices=["auto", "multi", "brave", "ddg", "exa", "tavily", "you", "searx", "langsearch"],
        default="auto",
    )
    parser.add_argument("--brave_pages", type=int, default=10)
    parser.add_argument("--ddg_max_results", type=int, default=50)
    parser.add_argument("--exa_num_results", type=int, default=100)
    parser.add_argument("--tavily_max", type=int, default=20)
    parser.add_argument("--tavily_topic", choices=["general", "news", "finance"], default="general")
    parser.add_argument("--you_num", dest="you_num_results", type=int, default=20)
    parser.add_argument("--searx_k", type=int, default=10)
    args = parser.parse_args()

    conn = WebConnector(
        mode=args.mode,
        brave_pages=args.brave_pages,
        ddg_max_results=args.ddg_max_results,
        exa_num_results=args.exa_num_results,
        tavily_max_results=args.tavily_max,
        tavily_topic=args.tavily_topic,
        you_num_results=args.you_num_results,
        searx_k=args.searx_k,
    )
    resp = conn.search(args.query)
    print(f"Mode     : {resp.provider}")
    print(f"Query    : {resp.query}")
    if resp.meta:
        print(f"Meta     : {resp.meta}")
    print(f"Total hits: {len(resp.hits)}")
    for i, h in enumerate(resp.hits[: min(10, len(resp.hits))], 1):
        print(f"\n[{i}] {h.title or '(no title)'}")
        print(f"    {h.url or '(no url)'}")
        if h.snippet:
            print(f"    {h.snippet[:180]}{'…' if len(h.snippet) > 180 else ''}")
