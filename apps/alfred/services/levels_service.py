from __future__ import annotations

from dataclasses import dataclass

from alfred.connectors.firecrawl_connector import FirecrawlClient
from alfred.connectors.web_connector import SearchHit, WebConnector
from alfred.core.rate_limit import web_rate_limiter
from alfred.schemas.company_insights import SourceInfo, SourceProvider


@dataclass
class LevelsService:
    """Public-only Levels.fyi compensation signal collector via web search + scraping."""

    web: WebConnector
    firecrawl: FirecrawlClient
    max_hits: int = 4

    def _search(self, query: str) -> list[SearchHit]:
        res = self.web.search(query, num_results=max(1, self.max_hits))
        return res.hits[: self.max_hits]

    def _scrape(self, url: str) -> tuple[str | None, str | None]:
        web_rate_limiter.wait("levels")
        resp = self.firecrawl.scrape(url, render_js=True)
        if not resp.success:
            err = resp.error if isinstance(resp.error, str) else str(resp.error)
            return None, err
        return resp.markdown, None

    def get_compensation_sources_sync(
        self, company_name: str, *, role: str | None = None
    ) -> tuple[list[dict[str, str | None]], list[SourceInfo]]:
        company = (company_name or "").strip()
        if not company:
            return [], []

        # Keep queries conservative; Levels pages are fairly structured but may render via JS.
        role_part = f'"{role}"' if role and role.strip() else ""
        query = f'site:levels.fyi "{company}" {role_part} (compensation OR salary OR "total compensation" OR TC)'
        hits = self._search(query)

        sources: list[SourceInfo] = []
        pages: list[dict[str, str | None]] = []
        for hit in hits:
            if not hit.url:
                continue
            markdown, error = self._scrape(hit.url)
            sources.append(
                SourceInfo(
                    provider=SourceProvider.levels,
                    url=hit.url,
                    title=hit.title,
                    error=error,
                )
            )
            pages.append({"url": hit.url, "title": hit.title, "markdown": markdown})
        return pages, sources
