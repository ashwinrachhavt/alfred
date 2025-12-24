from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Any, Iterable, Sequence

from alfred.connectors.firecrawl_connector import FirecrawlClient, FirecrawlResponse
from alfred.connectors.web_connector import SearchHit, SearchResponse, WebConnector
from alfred.core.settings import settings
from alfred.schemas.interview_questions import (
    InterviewQuestionsReport,
    QuestionItem,
    QuestionSource,
)

logger = logging.getLogger(__name__)

# Heuristic patterns that often show up as interview questions even without a '?'
QUESTION_PREFIXES = (
    "design ",
    "how would",
    "how do you",
    "walk me through",
    "tell me about",
    "what is your approach",
    "explain",
    "implement",
    "why ",
)

CATEGORY_KEYWORDS: dict[str, tuple[str, ...]] = {
    "system_design": (
        "design",
        "architecture",
        "scale",
        "scalable",
        "api",
        "throughput",
        "latency",
        "cache",
        "queue",
        "database",
        "distributed",
        "replication",
        "microservice",
    ),
    "coding": (
        "array",
        "string",
        "linked list",
        "hash",
        "tree",
        "graph",
        "trie",
        "dynamic programming",
        "complexity",
        "two sum",
        "binary search",
        "algorithm",
        "leetcode",
    ),
    "behavioral": (
        "tell me about",
        "conflict",
        "challenge",
        "failure",
        "leadership",
        "team",
        "strength",
        "weakness",
        "culture",
        "why",
    ),
    "ml_ai": (
        "machine learning",
        "model",
        "dataset",
        "inference",
        "training",
        "vector",
        "embedding",
        "prompt",
        "llm",
        "pipeline",
        "feature store",
    ),
}


def _dedupe_urls(hits: Sequence[SearchHit]) -> list[SearchHit]:
    seen: set[str] = set()
    deduped: list[SearchHit] = []
    for hit in hits:
        url = (hit.url or "").strip()
        if not url:
            continue
        key = url.lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(hit)
    return deduped


def _clean_line(text: str) -> str:
    cleaned = re.sub(r"^[>\-*\u2022\•\s]+", "", text.strip())
    cleaned = re.sub(r"^[0-9]+\s*[\).\]]\s*", "", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.strip()


@dataclass
class InterviewQuestionsService:
    """Harvest interview questions for a company/role via search + Firecrawl."""

    primary_search: WebConnector | None = None
    fallback_search: WebConnector | None = None
    firecrawl: FirecrawlClient | None = None
    search_results: int = 8
    firecrawl_search_results: int = 6
    render_js: bool = False

    def __post_init__(self) -> None:
        if self.primary_search is None:
            self.primary_search = WebConnector(mode="searx", searx_k=self.search_results)
        if self.fallback_search is None:
            self.fallback_search = WebConnector(mode="multi", searx_k=self.search_results)
        if self.firecrawl is None:
            self.firecrawl = FirecrawlClient(
                base_url=settings.firecrawl_base_url, timeout=settings.firecrawl_timeout
            )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
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
        if not company:
            raise ValueError("company is required")

        normalized_role = (role or "Software Engineer").strip() or "Software Engineer"
        queries = self._build_queries(company, normalized_role)

        warnings: list[str] = []
        search_meta: list[dict[str, Any]] = []

        search_hits, search_meta = self._run_searches(queries)
        fc_hits: list[SearchHit] = []
        if use_firecrawl_search:
            fc_hits = self._run_firecrawl_searches(queries[:2])

        merged_hits = _dedupe_urls(search_hits + fc_hits)
        capped_hits = merged_hits[: max(1, min(int(max_sources), 30))]

        sources: list[QuestionSource] = []
        for hit in capped_hits:
            src = self._build_source(hit)
            sources.append(src)
            if src.error:
                warnings.append(src.error)

        questions = self._aggregate_questions(sources, max_questions=max_questions)

        meta = {
            "searches": search_meta,
            "firecrawl_search_used": bool(use_firecrawl_search),
            "total_sources": len(sources),
        }

        return InterviewQuestionsReport(
            company=company,
            role=normalized_role,
            queries=queries,
            total_unique_questions=len(questions),
            questions=questions,
            sources=sources,
            warnings=list(dict.fromkeys(warnings)),
            meta=meta,
        )

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------
    def _build_queries(self, company: str, role: str) -> list[str]:
        base = f"{company} {role}"
        return [
            f"{base} interview questions",
            f"{base} coding interview questions",
            f"{base} system design interview",
            f"{base} behavioral interview questions",
            f"{company} interview questions glassdoor",
            f"{company} interview questions blind",
            f"{company} {role} onsite interview experience",
        ]

    def _run_searches(self, queries: Iterable[str]) -> tuple[list[SearchHit], list[dict[str, Any]]]:
        hits: list[SearchHit] = []
        meta: list[dict[str, Any]] = []
        for query in queries:
            try:
                resp = self.primary_search.search(query, num_results=self.search_results)  # type: ignore[arg-type]
            except Exception as exc:  # pragma: no cover - network failure
                logger.info("Primary search failed (%s): %s", query, exc)
                resp = None

            if resp is None or (resp.meta and resp.meta.get("status") == "unconfigured"):
                try:
                    resp = self.fallback_search.search(query, num_results=self.search_results)  # type: ignore[arg-type]
                except Exception as exc:  # pragma: no cover - network failure
                    meta.append({"query": query, "provider": "error", "error": str(exc)})
                    continue

            if isinstance(resp, SearchResponse):
                hits.extend(resp.hits[: self.search_results])
                meta.append(
                    {
                        "query": query,
                        "provider": resp.provider,
                        "results": len(resp.hits),
                        "meta": resp.meta,
                    }
                )
        return hits, meta

    def _run_firecrawl_searches(self, queries: Sequence[str]) -> list[SearchHit]:
        all_hits: list[SearchHit] = []
        for query in queries:
            try:
                resp = self.firecrawl.search(query, max_results=self.firecrawl_search_results)  # type: ignore[call-arg]
            except Exception as exc:  # pragma: no cover - network failure
                logger.info("Firecrawl search failed (%s): %s", query, exc)
                continue
            if not isinstance(resp, FirecrawlResponse) or not resp.success or not resp.data:
                continue
            all_hits.extend(self._normalize_firecrawl_hits(resp))
        return all_hits[: self.firecrawl_search_results * max(1, len(queries))]

    def _normalize_firecrawl_hits(self, resp: FirecrawlResponse) -> list[SearchHit]:
        payload = resp.data
        items: list[Any] = []
        if isinstance(payload, list):
            items = payload
        elif isinstance(payload, dict):
            for key in ("data", "results", "items"):
                val = payload.get(key)
                if isinstance(val, list):
                    items = val
                    break
            if not items:
                items = [payload]

        hits: list[SearchHit] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            url = item.get("url") or item.get("link") or item.get("source")
            title = item.get("title") or item.get("pageTitle")
            snippet = item.get("content") or item.get("snippet") or item.get("description")
            hits.append(
                SearchHit(title=title, url=url, snippet=snippet, source="firecrawl", raw=item)
            )
        return hits

    def _build_source(self, hit: SearchHit) -> QuestionSource:
        markdown: str | None = None
        error: str | None = None
        if hit.url:
            resp = self.firecrawl.scrape(hit.url, render_js=self.render_js)  # type: ignore[arg-type]
            if resp.success:
                markdown = resp.markdown or _coerce_markdown(resp.data)
            else:
                err_msg = resp.error if isinstance(resp.error, str) else str(resp.error)
                error = f"Failed to scrape {hit.url}: {err_msg}"
        else:
            error = "Search hit missing URL; skipped scrape"

        questions = self._extract_questions(markdown)
        if hit.snippet:
            questions.extend(self._extract_questions(hit.snippet))
        questions = self._dedupe_questions(questions)

        return QuestionSource(
            url=hit.url,
            title=hit.title,
            snippet=hit.snippet,
            provider=hit.source,
            questions=questions,
            error=error,
        )

    def _extract_questions(self, text: str | None) -> list[str]:
        if not text:
            return []
        cleaned_lines = []
        for raw in text.splitlines():
            candidate = _clean_line(raw)
            if not candidate or len(candidate) < 8:
                continue
            if len(candidate) > 260:
                continue
            if candidate.count("?") > 1:
                fragments = [frag.strip() for frag in candidate.split("?") if frag.strip()]
                cleaned_lines.extend([f"{frag}?" for frag in fragments])
                continue
            if "?" in candidate:
                cleaned_lines.append(candidate if candidate.endswith("?") else f"{candidate}?")
                continue
            lower = candidate.lower()
            if any(lower.startswith(pref) for pref in QUESTION_PREFIXES):
                cleaned_lines.append(candidate if candidate.endswith("?") else f"{candidate}?")
        return self._dedupe_questions(cleaned_lines)

    def _categorize_question(self, question: str) -> list[str]:
        lowered = question.lower()
        categories: list[str] = []
        for name, keywords in CATEGORY_KEYWORDS.items():
            if any(term in lowered for term in keywords):
                categories.append(name)
        if not categories:
            categories.append("general")
        return categories

    def _aggregate_questions(
        self, sources: Sequence[QuestionSource], *, max_questions: int
    ) -> list[QuestionItem]:
        bucket: dict[str, dict[str, Any]] = {}
        for source in sources:
            for question in source.questions:
                normalized = question.strip()
                if not normalized:
                    continue
                key = normalized.lower()
                entry = bucket.setdefault(
                    key,
                    {
                        "question": normalized if normalized.endswith("?") else f"{normalized}?",
                        "count": 0,
                        "sources": set(),
                        "categories": set(),
                    },
                )
                entry["count"] += 1
                if source.url:
                    entry["sources"].add(source.url)
                entry["categories"].update(self._categorize_question(entry["question"]))

        ordered = sorted(bucket.values(), key=lambda x: (-x["count"], x["question"]))
        limited = ordered[: max(1, min(int(max_questions), len(ordered)))]
        out: list[QuestionItem] = []
        for entry in limited:
            out.append(
                QuestionItem(
                    question=entry["question"],
                    categories=sorted(entry["categories"]),
                    occurrences=entry["count"],
                    sources=sorted(entry["sources"]),
                )
            )
        return out

    @staticmethod
    def _dedupe_questions(items: Iterable[str]) -> list[str]:
        seen: set[str] = set()
        out: list[str] = []
        for item in items:
            key = item.strip().rstrip(" ?").lower()
            if not key or key in seen:
                continue
            seen.add(key)
            normalized = item.strip()
            normalized = normalized if normalized.endswith("?") else f"{normalized}?"
            out.append(normalized)
        return out


def _coerce_markdown(payload: Any) -> str | None:
    if not payload:
        return None
    if isinstance(payload, str):
        return payload
    if isinstance(payload, dict):
        for key in ("markdown", "content", "text"):
            val = payload.get(key)
            if isinstance(val, str) and val.strip():
                return val.strip()
    return None
