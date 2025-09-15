from __future__ import annotations

import asyncio
import json
import os
from dataclasses import dataclass
from typing import Any, List, Literal, Optional, Sequence

Provider = Literal["brave", "ddg", "exa", "tavily", "you"]
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
            items = json.loads(items)
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

        self.tool = BraveSearch.from_api_key(api_key=api_key, search_kwargs={"count": min(count, 20)})

    def search(self, query: str, pages: int = 10) -> SearchResponse:
        pages = max(1, min(pages, 10))
        all_hits: List[SearchHit] = []
        for offset in range(pages):
            self.tool.search_wrapper.search_kwargs.update({"offset": offset})
            res = self.tool.run(query)
            all_hits.extend(_normalize_list_result(res, "brave"))
        return SearchResponse(provider="brave", query=query, hits=_dedupe_by_url(all_hits), meta={"pages": pages, "count": self.tool.search_wrapper.search_kwargs.get("count")})


class DDGClient:
    def __init__(self, max_results: int = 50, output_format: Literal["list", "json", "markdown"] = "list"):
        from langchain_community.tools import DuckDuckGoSearchResults
        from langchain_community.utilities import DuckDuckGoSearchAPIWrapper

        api = DuckDuckGoSearchAPIWrapper(max_results=max_results)
        self.tool = DuckDuckGoSearchResults(api_wrapper=api, output_format=output_format)

    def search(self, query: str) -> SearchResponse:
        res = self.tool.invoke(query)
        hits = _normalize_list_result(res, "ddg")
        return SearchResponse(provider="ddg", query=query, hits=_dedupe_by_url(hits))


class ExaClient:
    def __init__(self, default_num_results: int = 100, **kwargs: Any):
        if not _env("EXA_API_KEY"):
            raise RuntimeError("EXA_API_KEY is not set")
        from langchain_exa import ExaSearchResults

        self.tool = ExaSearchResults(max_results=default_num_results, **kwargs)

    def search(self, query: str, num_results: int = 100, text_contents_options: Any = None, highlights: bool = True, **kwargs: Any) -> SearchResponse:
        if text_contents_options is None:
            text_contents_options = {"max_characters": 3000}
        payload = {"query": query, "num_results": max(1, min(num_results, 100)), "highlights": highlights, "text_contents_options": text_contents_options}
        payload.update(kwargs)
        res = self.tool.invoke(payload)
        hits = _normalize_list_result(res, "exa")
        return SearchResponse(provider="exa", query=query, hits=_dedupe_by_url(hits))


class TavilyClient:
    def __init__(self, max_results: int = 20, topic: Literal["general", "news", "finance"] = "general", include_answer: bool = True, include_raw_content: bool = True, **kwargs: Any):
        if not _env("TAVILY_API_KEY"):
            raise RuntimeError("TAVILY_API_KEY is not set")
        from langchain_tavily import TavilySearch

        self.tool = TavilySearch(max_results=max_results, topic=topic, include_answer=include_answer, include_raw_content=include_raw_content, **kwargs)

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


class WebConnector:
    def __init__(self, mode: Mode = "auto", *, brave_count: int = 20, brave_pages: int = 10, ddg_max_results: int = 50, exa_num_results: int = 100, tavily_max_results: int = 20, tavily_topic: Literal["general", "news", "finance"] = "general", you_num_results: int = 20):
        self.mode = mode
        self._init_clients(brave_count, ddg_max_results, exa_num_results, tavily_max_results, tavily_topic, you_num_results)
        self._brave_pages_default = brave_pages

    def _init_clients(self, brave_count: int, ddg_max_results: int, exa_num_results: int, tavily_max_results: int, tavily_topic: str, you_num_results: int) -> None:
        self.clients: dict[Provider, Any] = {}
        if _env("EXA_API_KEY"):
            self.clients["exa"] = ExaClient(default_num_results=exa_num_results)
        if _env("TAVILY_API_KEY"):
            self.clients["tavily"] = TavilyClient(max_results=tavily_max_results, topic=tavily_topic)
        if _env("BRAVE_SEARCH_API_KEY"):
            self.clients["brave"] = BraveClient(count=brave_count)
        if _env("YDC_API_KEY"):
            self.clients["you"] = YouClient(num_web_results=you_num_results)
        self.clients["ddg"] = DDGClient(max_results=ddg_max_results)

    def _resolve_auto(self) -> Provider:
        for p in ("exa", "tavily", "brave", "you", "ddg"):
            if p in self.clients:
                return p  # type: ignore
        return "ddg"

    def _collect_enabled(self) -> List[Provider]:
        order: List[Provider] = ["exa", "tavily", "brave", "you", "ddg"]
        return [p for p in order if p in self.clients]

    def _search_multi(self, query: str, **kwargs: Any) -> SearchResponse:
        providers = self._collect_enabled()
        loop = asyncio.get_event_loop()

        def call(p: Provider):
            c = self.clients[p]
            if p == "brave":
                return c.search(query, pages=self._brave_pages_default)
            if p == "exa":
                return c.search(query, num_results=kwargs.get("num_results", 100))
            return c.search(query)

        tasks = [loop.run_in_executor(None, call, p) for p in providers]
        results: List[SearchResponse] = loop.run_until_complete(asyncio.gather(*tasks))
        merged = _dedupe_by_url([h for r in results for h in r.hits])
        return SearchResponse(provider="multi", query=query, hits=merged, meta={"providers": providers, "sizes": {r.provider: len(r.hits) for r in results}})

    def search(self, query: str, *, pages: Optional[int] = None, **kwargs: Any) -> SearchResponse:
        if self.mode == "multi":
            return self._search_multi(query, **kwargs)
        provider: Provider = self._resolve_auto() if self.mode == "auto" else self.mode
        client = self.clients.get(provider)
        if not client:
            raise RuntimeError(f"Provider '{provider}' is not configured")
        if provider == "brave":
            return client.search(query, pages=pages or self._brave_pages_default)
        if provider == "exa":
            num = kwargs.pop("num_results", 100)
            return client.search(query, num_results=num, **kwargs)
        return client.search(query, **kwargs)

    async def asearch(self, query: str, **kwargs: Any) -> SearchResponse:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, lambda: self.search(query, **kwargs))


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="WebConnector quick test")
    parser.add_argument("query", type=str)
    parser.add_argument("--mode", choices=["auto", "multi", "brave", "ddg", "exa", "tavily", "you"], default="auto")
    parser.add_argument("--brave_pages", type=int, default=10)
    parser.add_argument("--ddg_max_results", type=int, default=50)
    parser.add_argument("--exa_num_results", type=int, default=100)
    parser.add_argument("--tavily_max", type=int, default=20)
    parser.add_argument("--tavily_topic", choices=["general", "news", "finance"], default="general")
    parser.add_argument("--you_num", dest="you_num_results", type=int, default=20)
    args = parser.parse_args()

    conn = WebConnector(mode=args.mode, brave_pages=args.brave_pages, ddg_max_results=args.ddg_max_results, exa_num_results=args.exa_num_results, tavily_max_results=args.tavily_max, tavily_topic=args.tavily_topic, you_num_results=args.you_num_results)
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

