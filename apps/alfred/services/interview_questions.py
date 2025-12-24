from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Iterable

from alfred.connectors.firecrawl_connector import FirecrawlClient, FirecrawlResponse
from alfred.connectors.web_connector import SearchHit, SearchResponse, WebConnector
from alfred.core.settings import settings
from alfred.schemas.interview_questions import (
    InterviewQuestionsReport,
    QuestionItem,
    QuestionSource,
)

_WS_RE = re.compile(r"\s+")
_BULLET_PREFIX_RE = re.compile(r"^\s*(?:[-*•]+|\d+[.)])\s*")


def _clean_line(line: str) -> str:
    cleaned = _BULLET_PREFIX_RE.sub("", line.strip())
    cleaned = cleaned.strip(" \t-–—•*")
    cleaned = _WS_RE.sub(" ", cleaned).strip()
    return cleaned


def _looks_like_question(text: str) -> bool:
    s = (text or "").strip()
    if not s:
        return False
    if "?" in s:
        return True

    lower = s.lower()
    starters = (
        "how ",
        "what ",
        "why ",
        "when ",
        "where ",
        "which ",
        "who ",
        "explain ",
        "describe ",
        "tell me ",
        "walk me ",
        "talk me ",
        "give an example",
        "can you ",
        "could you ",
        "would you ",
        "design ",
        "implement ",
        "compare ",
        "define ",
    )
    return lower.startswith(starters)


def _normalize_question(text: str) -> str:
    s = _WS_RE.sub(" ", (text or "").strip()).strip()
    # Normalize trailing punctuation.
    while s.endswith((".", "!", ":")):
        s = s[:-1].rstrip()
    if not s.endswith("?"):
        s += "?"
    return s


def _extract_questions(text: str | None, *, max_questions: int = 12) -> list[str]:
    if not text:
        return []

    out: list[str] = []
    seen: set[str] = set()
    for raw in text.splitlines():
        line = _clean_line(raw)
        if not line:
            continue
        if "http" in line.lower():
            continue
        if len(line) > 220:
            continue
        if not _looks_like_question(line):
            continue

        q = _normalize_question(line)
        key = q.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(q)
        if len(out) >= max(1, int(max_questions)):
            break
    return out


def _categorize(question: str) -> list[str]:
    q = (question or "").lower()
    categories: list[str] = []

    behavioral_kw = (
        "conflict",
        "coworker",
        "team",
        "leadership",
        "failure",
        "challenge",
        "feedback",
        "strength",
        "weakness",
        "disagree",
        "stakeholder",
    )
    system_kw = (
        "system design",
        "design ",
        "architecture",
        "distributed",
        "cap theorem",
        "cache",
        "load balancer",
        "throughput",
        "latency",
        "consistency",
        "partition",
        "database",
        "feature store",
        "uber",
        "scal",
    )
    coding_kw = (
        "algorithm",
        "data structure",
        "complexity",
        "big o",
        "leetcode",
        "array",
        "string",
        "graph",
        "tree",
        "dynamic programming",
        "dp",
        "hash",
        "sort",
        "binary search",
        "two pointers",
        "stack",
        "queue",
    )
    ml_kw = (
        "model",
        "training",
        "overfitting",
        "embedding",
        "transformer",
        "llm",
        "prompt",
    )

    if any(k in q for k in behavioral_kw):
        categories.append("behavioral")
    if any(k in q for k in system_kw):
        categories.append("system_design")
    if any(k in q for k in coding_kw):
        categories.append("coding")
    if any(k in q for k in ml_kw):
        categories.append("ml")

    return categories or ["general"]


def _unique_sources(urls: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for u in urls:
        key = (u or "").strip().lower()
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(u)
    return out


@dataclass
class InterviewQuestionsService:
    """Collect and normalize interview questions from public sources."""

    primary_search: Any | None = None
    fallback_search: Any | None = None
    firecrawl: Any | None = None
    search_results: int = 8
    firecrawl_search_results: int = 6

    def __post_init__(self) -> None:
        if self.primary_search is None:
            self.primary_search = WebConnector(mode="auto", searx_k=self.search_results)
        if self.fallback_search is None:
            self.fallback_search = self.primary_search
        if self.firecrawl is None:
            self.firecrawl = FirecrawlClient(
                base_url=settings.firecrawl_base_url,
                timeout=settings.firecrawl_timeout,
            )

    def generate_report(
        self,
        company: str,
        *,
        role: str | None = None,
        max_sources: int = 12,
        max_questions: int = 60,
        use_firecrawl_search: bool = True,
    ) -> InterviewQuestionsReport:
        company = (company or "").strip()
        role_clean = (role or "").strip() or None
        if not company:
            raise ValueError("company must be non-empty")

        max_sources = max(1, int(max_sources))
        max_questions = max(1, int(max_questions))

        base = f"{company} {role_clean}".strip()
        queries = [
            f"{base} coding interview questions".strip(),
            f"{base} interview questions".strip(),
        ]

        warnings: list[str] = []
        sources: list[QuestionSource] = []
        urls: list[str] = []

        def _search(conn: Any, query: str) -> SearchResponse | None:
            try:
                return conn.search(query)
            except Exception as exc:
                warnings.append(f"Search failed for query '{query}': {exc}")
                return None

        for q in queries:
            res = _search(self.primary_search, q)
            if res is None or not getattr(res, "hits", None):
                res = _search(self.fallback_search, q)
            if res is None:
                continue
            hits = list(res.hits or [])[: max(1, self.search_results)]
            for hit in hits:
                if not isinstance(hit, SearchHit) or not hit.url:
                    continue
                urls.append(hit.url)
                sources.append(
                    QuestionSource(
                        url=hit.url,
                        title=hit.title,
                        snippet=hit.snippet,
                        provider=str(getattr(res, "provider", None) or hit.source),
                    )
                )

        if use_firecrawl_search and self.firecrawl is not None:
            try:
                fire = self.firecrawl.search(
                    f"{base} interview questions".strip(),
                    max_results=max(1, int(self.firecrawl_search_results)),
                )
            except Exception as exc:  # pragma: no cover - network/provider errors
                fire = FirecrawlResponse(success=False, error=str(exc))
            if fire.success and isinstance(fire.data, list):
                for item in fire.data[: max(1, self.firecrawl_search_results)]:
                    if not isinstance(item, dict):
                        continue
                    url = item.get("url")
                    if not isinstance(url, str) or not url.strip():
                        continue
                    urls.append(url)
                    content = item.get("content")
                    extracted = _extract_questions(
                        content if isinstance(content, str) else None, max_questions=8
                    )
                    sources.append(
                        QuestionSource(
                            url=url,
                            title=item.get("title") if isinstance(item.get("title"), str) else None,
                            snippet=content if isinstance(content, str) else None,
                            provider="firecrawl",
                            questions=extracted,
                        )
                    )

        urls = _unique_sources(urls)[:max_sources]

        def _scrape(url: str) -> tuple[str | None, str | None]:
            try:
                resp = self.firecrawl.scrape(url, render_js=False)
            except Exception as exc:  # pragma: no cover - network/provider errors
                return None, str(exc)
            if not getattr(resp, "success", False):
                err = getattr(resp, "error", None)
                return None, err if isinstance(err, str) else str(err)
            return getattr(resp, "markdown", None), None

        by_url: dict[str, QuestionSource] = {s.url: s for s in sources if s.url}
        for url in urls:
            markdown, error = _scrape(url)
            qs = _extract_questions(markdown, max_questions=16)
            existing = by_url.get(url)
            if existing is None:
                sources.append(
                    QuestionSource(url=url, provider="firecrawl", questions=qs, error=error)
                )
            else:
                existing.error = existing.error or error
                existing.questions = _unique_sources(existing.questions + qs)  # type: ignore[arg-type]

        # Aggregate questions across sources.
        items: dict[str, QuestionItem] = {}
        for src in sources:
            for q in src.questions:
                norm = _normalize_question(q)
                key = norm.lower()
                entry = items.get(key)
                if entry is None:
                    entry = QuestionItem(
                        question=norm,
                        categories=_categorize(norm),
                        occurrences=0,
                        sources=[],
                    )
                    items[key] = entry
                entry.occurrences += 1
                if src.url and src.url not in entry.sources:
                    entry.sources.append(src.url)

        question_list = sorted(
            items.values(),
            key=lambda x: (-x.occurrences, x.question.lower()),
        )[:max_questions]

        return InterviewQuestionsReport(
            company=company,
            role=role_clean,
            queries=queries,
            total_unique_questions=len(items),
            questions=question_list,
            sources=sources[:max_sources],
            warnings=warnings,
            meta={"sources_considered": len(urls)},
        )


__all__ = ["InterviewQuestionsService"]
