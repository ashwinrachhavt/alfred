"""Company research pipeline powered by SearxNG + Firecrawl + GPT."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, List, cast

from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

from alfred.connectors.firecrawl_connector import FirecrawlClient
from alfred.connectors.web_connector import SearchHit, WebConnector
from alfred.core.settings import settings
from alfred.prompts import load_prompt
from alfred.services.mongo import MongoService

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = load_prompt("company_researcher", "system.md")
REPORT_PROMPT = load_prompt("company_researcher", "deep.md")
MAX_CONTEXT_CHARS = 40_000
TRIMMED_MARKDOWN_CHARS = 12_000


@dataclass
class EnrichedSource:
    title: str | None
    url: str | None
    snippet: str | None
    markdown: str | None
    provider: str | None
    error: str | None = None

    def to_payload(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "url": self.url,
            "snippet": self.snippet,
            "markdown": self.markdown,
            "provider": self.provider,
            "error": self.error,
        }


class ReportSection(BaseModel):
    name: str = Field(..., description="Section title such as 'Market Landscape'.")
    summary: str = Field(..., description="Short paragraph summarizing this section.")
    insights: List[str] = Field(
        default_factory=list,
        description="Bullet insights with bracketed source citations.",
    )


class CompanyResearchReport(BaseModel):
    company: str
    executive_summary: str
    sections: List[ReportSection]
    risks: List[str] = Field(default_factory=list)
    opportunities: List[str] = Field(default_factory=list)
    recommended_actions: List[str] = Field(default_factory=list)
    references: List[str] = Field(default_factory=list)


class CompanyResearchService:
    def __init__(
        self,
        *,
        search_results: int = 8,
        firecrawl_render_js: bool = False,
    ) -> None:
        self.search_results = max(1, search_results)
        self._primary_search = WebConnector(mode="searx", searx_k=self.search_results)
        self._fallback_search = WebConnector(mode="multi", searx_k=self.search_results)
        self._firecrawl = FirecrawlClient(
            base_url=settings.firecrawl_base_url,
            timeout=settings.firecrawl_timeout,
        )
        self._firecrawl_render_js = firecrawl_render_js
        self._mongo = MongoService(default_collection=settings.company_research_collection)
        self._model_name = settings.company_research_model
        self._llm = ChatOpenAI(
            model=self._model_name,
            temperature=0.15,
            api_key=(
                settings.openai_api_key.get_secret_value() if settings.openai_api_key else None
            ),
            base_url=settings.openai_base_url,
            organization=settings.openai_organization,
        )
        self._structured_llm = self._llm.with_structured_output(CompanyResearchReport)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def generate_report(self, company: str, *, refresh: bool = False) -> dict[str, Any]:
        company = company.strip()
        if not company:
            raise ValueError("Company name is required")

        if not refresh:
            cached = self._find_latest(company)
            if cached:
                return cached

        sources, search_meta = self._collect_sources(company)
        report = self._run_llm(company, sources)
        references = report.references or []
        references.extend([src.url for src in sources if src.url])
        sanitized_refs = list(dict.fromkeys([ref for ref in references if ref]))
        payload = {
            "company": company,
            "model": self._model_name,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "report": report.dict(),
            "sources": [src.to_payload() for src in sources],
            "search": search_meta,
        }
        payload["report"]["references"] = sanitized_refs

        self._mongo.update_one({"company": company}, {"$set": payload}, upsert=True)
        stored = self._find_latest(company)
        return stored or payload

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------
    def _collect_sources(self, company: str) -> tuple[list[EnrichedSource], dict[str, Any]]:
        primary = self._search(company, self._primary_search)
        hits = primary.hits[: self.search_results]
        meta = {"provider": primary.provider, "hits": len(hits), "meta": primary.meta}
        if not hits and primary.meta and primary.meta.get("status") == "unconfigured":
            logger.info("SearxNG unavailable; falling back to multi-provider search")
            fallback = self._search(company, self._fallback_search)
            hits = fallback.hits[: self.search_results]
            meta = {"provider": fallback.provider, "hits": len(hits), "meta": fallback.meta}
        sources = [self._enrich_hit(hit, meta["provider"]) for hit in hits]
        return sources, meta

    def _search(self, company: str, connector: WebConnector):
        try:
            return connector.search(company, num_results=self.search_results)
        except Exception as exc:  # pragma: no cover - network failure
            logger.warning("Web search failed: %s", exc)
            return connector.search(company)

    def _enrich_hit(self, hit: SearchHit, provider: str | None) -> EnrichedSource:
        markdown: str | None = None
        error: str | None = None
        if hit.url:
            markdown, error = self._fetch_markdown(hit.url)
        return EnrichedSource(
            title=hit.title,
            url=hit.url,
            snippet=hit.snippet,
            markdown=markdown,
            provider=provider,
            error=error,
        )

    def _fetch_markdown(self, url: str) -> tuple[str | None, str | None]:
        response = self._firecrawl.scrape(url, render_js=self._firecrawl_render_js)
        if response.success:
            text = response.markdown
            if not text and isinstance(response.data, dict):
                data_markdown = response.data.get("markdown")
                if isinstance(data_markdown, str):
                    text = data_markdown
            if text:
                return self._trim(text), None
            return None, None
        error = response.error
        return None, error if isinstance(error, str) else str(error)

    def _trim(self, text: str) -> str:
        text = text.strip()
        if len(text) <= TRIMMED_MARKDOWN_CHARS:
            return text
        return text[:TRIMMED_MARKDOWN_CHARS] + "\n…"

    def _run_llm(self, company: str, sources: list[EnrichedSource]) -> CompanyResearchReport:
        context = self._render_context(sources)
        user_prompt = REPORT_PROMPT.format(company=company, sources=context)
        return cast(
            CompanyResearchReport,
            self._structured_llm.invoke(
                [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ]
            ),
        )

    def _render_context(self, sources: list[EnrichedSource]) -> str:
        if not sources:
            return "(No contextual packets were retrieved. Flag all missing data explicitly.)"
        parts: list[str] = []
        running_length = 0
        for idx, src in enumerate(sources, start=1):
            markdown = src.markdown or ""
            snippet = src.snippet or ""
            block = (
                f"Source {idx}\nTitle: {src.title or 'N/A'}\nURL: {src.url or 'N/A'}\n"
                f"Snippet: {snippet}\nContent:\n{markdown}"
            )
            if running_length + len(block) > MAX_CONTEXT_CHARS:
                break
            running_length += len(block)
            parts.append(block)
        return "\n\n---\n\n".join(parts)

    def _find_latest(self, company: str) -> dict[str, Any] | None:
        record = self._mongo.find_one({"company": company})
        if not record:
            return None
        payload = dict(record)
        record_id = payload.pop("_id", None)
        if record_id is not None:
            payload["id"] = str(record_id)
        return payload


def generate_company_research(company: str, *, refresh: bool = False) -> dict[str, Any]:
    service = CompanyResearchService()
    return service.generate_report(company, refresh=refresh)
