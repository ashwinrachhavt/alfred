from __future__ import annotations

import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass

from alfred.connectors.firecrawl_connector import FirecrawlClient
from alfred.connectors.web_connector import SearchHit, WebConnector
from alfred.core.rate_limit import web_rate_limiter
from alfred.schemas.company_insights import (
    DiscussionPost,
    InterviewExperience,
    SourceInfo,
    SourceProvider,
)
from alfred.services.utils import extract_questions_qmark_only


def _excerpt(markdown: str | None, *, max_chars: int = 500) -> str | None:
    if not markdown:
        return None
    text = re.sub(r"\\s+", " ", markdown).strip()
    if not text:
        return None
    return text[:max_chars] + ("…" if len(text) > max_chars else "")


@dataclass
class BlindService:
    """Public-only TeamBlind (teamblind.com) signal collector via web search + scraping.

    Notes:
    - TeamBlind content is often gated; this service only collects what is publicly accessible.
    - No authentication/cookie handling is implemented.
    """

    web: WebConnector
    firecrawl: FirecrawlClient
    max_hits: int = 6

    def _search(self, query: str) -> list[SearchHit]:
        res = self.web.search(query, num_results=max(1, self.max_hits))
        return res.hits[: self.max_hits]

    def _scrape(self, url: str) -> tuple[str | None, str | None]:
        web_rate_limiter.wait("blind")
        resp = self.firecrawl.scrape(url, render_js=False)
        if not resp.success:
            err = resp.error if isinstance(resp.error, str) else str(resp.error)
            return None, err
        return resp.markdown, None

    def get_company_discussions_sync(
        self, company_name: str
    ) -> tuple[list[DiscussionPost], list[SourceInfo]]:
        company = (company_name or "").strip()
        if not company:
            return [], []

        query = f'site:teamblind.com "{company}" (culture OR "work life" OR wlb OR management OR salary OR compensation)'
        hits = self._search(query)

        posts: list[DiscussionPost] = []
        sources: list[SourceInfo] = []

        runnable_hits = [(idx, hit) for idx, hit in enumerate(hits) if hit.url]
        if not runnable_hits:
            return [], []

        max_workers = min(4, len(runnable_hits))
        results: dict[int, tuple[SearchHit, str | None, str | None]] = {}
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_map = {
                executor.submit(self._scrape, hit.url or ""): (idx, hit)
                for idx, hit in runnable_hits
            }
            for future in as_completed(future_map):
                idx, hit = future_map[future]
                try:
                    markdown, error = future.result()
                except Exception as exc:
                    markdown, error = None, str(exc)
                results[idx] = (hit, markdown, error)

        for idx in sorted(results):
            hit, markdown, error = results[idx]
            sources.append(
                SourceInfo(
                    provider=SourceProvider.blind,
                    url=hit.url,
                    title=hit.title,
                    error=error,
                )
            )
            posts.append(
                DiscussionPost(
                    source=SourceProvider.blind,
                    url=hit.url,
                    title=hit.title,
                    excerpt=_excerpt(markdown) or hit.snippet,
                    created_at=None,
                    tags=[],
                )
            )
        return posts, sources

    def search_interview_posts_sync(
        self, company_name: str
    ) -> tuple[list[InterviewExperience], list[SourceInfo]]:
        company = (company_name or "").strip()
        if not company:
            return [], []

        query = f'site:teamblind.com "{company}" interview questions'
        hits = self._search(query)

        interviews: list[InterviewExperience] = []
        sources: list[SourceInfo] = []

        runnable_hits = [(idx, hit) for idx, hit in enumerate(hits) if hit.url]
        if not runnable_hits:
            return [], []

        max_workers = min(4, len(runnable_hits))
        results: dict[int, tuple[SearchHit, str | None, str | None]] = {}
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_map = {
                executor.submit(self._scrape, hit.url or ""): (idx, hit)
                for idx, hit in runnable_hits
            }
            for future in as_completed(future_map):
                idx, hit = future_map[future]
                try:
                    markdown, error = future.result()
                except Exception as exc:
                    markdown, error = None, str(exc)
                results[idx] = (hit, markdown, error)

        for idx in sorted(results):
            hit, markdown, error = results[idx]
            sources.append(
                SourceInfo(
                    provider=SourceProvider.blind,
                    url=hit.url,
                    title=hit.title,
                    error=error,
                )
            )
            interviews.append(
                InterviewExperience(
                    source=SourceProvider.blind,
                    source_url=hit.url,
                    role=None,
                    location=None,
                    interview_date=None,
                    difficulty=None,
                    outcome=None,
                    process_summary=_excerpt(markdown) or hit.snippet,
                    questions=extract_questions_qmark_only(markdown),
                )
            )
        return interviews, sources
