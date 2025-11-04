"""Thin client wrappers around the Firecrawl API."""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from urllib.parse import urljoin

import requests
from pydantic import BaseModel


class FirecrawlResponse(BaseModel):
    success: bool
    data: Optional[Any] = None
    error: Optional[Any] = None
    markdown: Optional[str] = None
    status_code: Optional[int] = None


class FirecrawlClient:
    def __init__(self, base_url: str = "http://localhost:8010", timeout: int = 30):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def get(self, endpoint: str) -> FirecrawlResponse:
        return self._request("get", endpoint)

    def post(self, endpoint: str, payload: Dict[str, Any]) -> FirecrawlResponse:
        return self._request("post", endpoint, payload)

    def health(self) -> FirecrawlResponse:
        return self.get("/health")

    def scrape(self, url: str, render_js: bool = False) -> FirecrawlResponse:
        payload = {"url": url, "render_js": render_js}
        return self.post("/scrape", payload)

    def crawl(
        self,
        url: str,
        max_pages: int = 10,
        render_js: bool = False,
        include_sitemaps: bool = False,
    ) -> FirecrawlResponse:
        payload = {
            "url": url,
            "max_pages": max_pages,
            "render_js": render_js,
            "include_sitemaps": include_sitemaps,
        }
        return self.post("/crawl", payload)

    def crawl_status(self, crawl_id: str) -> FirecrawlResponse:
        return self.get(f"/crawl/{crawl_id}/status")

    def extract(
        self,
        urls: List[str],
        selectors: Optional[Dict[str, str]] = None,
        render_js: bool = False,
    ) -> FirecrawlResponse:
        payload: Dict[str, Any] = {"urls": urls, "render_js": render_js}
        if selectors:
            payload["selectors"] = selectors
        return self.post("/extract", payload)

    def search(self, query: str, max_results: int = 10) -> FirecrawlResponse:
        payload = {"query": query, "max_results": max_results}
        return self.post("/search", payload)

    def _request(
        self, method: str, endpoint: str, payload: Optional[Dict[str, Any]] = None
    ) -> FirecrawlResponse:
        url = urljoin(self.base_url + "/", endpoint.lstrip("/"))
        try:
            kwargs: Dict[str, Any] = {"timeout": self.timeout}
            if payload is not None:
                kwargs["json"] = payload
            response = requests.request(method=method.lower(), url=url, **kwargs)
            return self._unwrap_firecrawl(response)
        except requests.RequestException as exc:
            return FirecrawlResponse(success=False, error=str(exc))

    def _unwrap_firecrawl(self, response: requests.Response) -> FirecrawlResponse:
        try:
            payload: Any = response.json()
        except ValueError:
            payload = response.text or ""
        if response.ok:
            markdown = self._extract_markdown(payload)
            return FirecrawlResponse(
                success=True,
                data=payload,
                markdown=markdown,
                status_code=response.status_code,
            )
        return FirecrawlResponse(success=False, error=payload, status_code=response.status_code)

    def _extract_markdown(self, payload: Any) -> Optional[str]:
        if isinstance(payload, str):
            return payload
        if isinstance(payload, dict):
            direct = payload.get("markdown")
            if isinstance(direct, str):
                return direct
            nested = payload.get("data")
            if isinstance(nested, dict):
                nested_markdown = nested.get("markdown")
                if isinstance(nested_markdown, str):
                    return nested_markdown
        return None


if __name__ == "__main__":
    client = FirecrawlClient()

    print("Health:", client.health())
    print("Scrape:", client.scrape("https://www.airops.com/"))
    crawl_job = client.crawl("https://www.airops.com/")
    if (
        crawl_job.success
        and crawl_job.data
        and "data" in crawl_job.data
        and isinstance(crawl_job.data["data"], dict)
        and "id" in crawl_job.data["data"]
    ):
        crawl_id = crawl_job.data["data"]["id"]
        print("Crawl Job:", crawl_id)
        print("Crawl Status:", client.crawl_status(crawl_id))

    extract_job = client.extract(["https://www.airops.com/"])
    print("Extract:", extract_job)
