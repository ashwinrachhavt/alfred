"""Company research service.

This is the canonical module for the "company research" feature.
"""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, cast

import sqlalchemy as sa
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field
from sqlmodel import select

from alfred.connectors.firecrawl_connector import FirecrawlClient
from alfred.connectors.web_connector import SearchHit, WebConnector
from alfred.core.database import SessionLocal
from alfred.core.exceptions import ConfigurationError
from alfred.core.settings import settings
from alfred.core.utils import utcnow as _utcnow
from alfred.models.company import CompanyResearchReportRow
from alfred.prompts import load_prompt
from alfred.services.datastore import DataStoreService

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
    insights: list[str] = Field(
        default_factory=list,
        description="Bullet insights with bracketed source citations.",
    )


class CompanyResearchReport(BaseModel):
    company: str
    executive_summary: str
    sections: list[ReportSection]
    risks: list[str] = Field(default_factory=list)
    opportunities: list[str] = Field(default_factory=list)
    recommended_actions: list[str] = Field(default_factory=list)
    references: list[str] = Field(default_factory=list)


class CompanyResearchService:
    def __init__(
        self,
        *,
        search_results: int = 8,
        firecrawl_render_js: bool = False,
        primary_search: WebConnector | None = None,
        fallback_search: WebConnector | None = None,
        firecrawl: FirecrawlClient | None = None,
        store: DataStoreService | None = None,
    ) -> None:
        self.search_results = max(1, search_results)
        # Defer heavy init; allow DI for tests
        self._primary_search = primary_search
        self._fallback_search = fallback_search
        self._firecrawl = firecrawl
        self._firecrawl_render_js = firecrawl_render_js
        self._store = store
        self._model_name = settings.company_research_model
        self._llm = None
        self._structured_llm = None

    def _company_key(self, company: str) -> str:
        return (company or "").strip().lower()

    def _read_latest_from_db(self, company: str) -> dict[str, Any] | None:
        key = self._company_key(company)
        if not key:
            return None

        with SessionLocal() as session:
            row = session.exec(
                select(CompanyResearchReportRow).where(CompanyResearchReportRow.company_key == key)
            ).first()
            if row is None:
                return None

            payload: dict[str, Any] = dict(row.payload or {})
            payload.setdefault("company", row.company)
            payload["id"] = str(row.id)
            return payload

    def _upsert_latest_to_db(
        self,
        *,
        company: str,
        payload: dict[str, Any],
        model_name: str | None = None,
        generated_at: datetime | None = None,
    ) -> dict[str, Any]:
        key = self._company_key(company)
        if not key:
            raise ValueError("Company name is required")

        now = _utcnow()
        with SessionLocal() as session:
            row = session.exec(
                select(CompanyResearchReportRow).where(CompanyResearchReportRow.company_key == key)
            ).first()

            if row is None:
                row = CompanyResearchReportRow(
                    company_key=key,
                    company=company.strip(),
                    payload=payload,
                    model_name=model_name,
                    generated_at=generated_at,
                    created_at=now,
                    updated_at=now,
                )
                session.add(row)
            else:
                row.company = company.strip()
                row.payload = payload
                row.model_name = model_name
                row.generated_at = generated_at
                row.updated_at = now
                session.add(row)

            try:
                session.commit()
            except sa.exc.IntegrityError:
                session.rollback()
                row = session.exec(
                    select(CompanyResearchReportRow).where(
                        CompanyResearchReportRow.company_key == key
                    )
                ).first()
                if row is None:
                    raise
                row.company = company.strip()
                row.payload = payload
                row.model_name = model_name
                row.generated_at = generated_at
                row.updated_at = now
                session.add(row)
                session.commit()

            session.refresh(row)

            stored: dict[str, Any] = dict(row.payload or {})
            stored.setdefault("company", row.company)
            stored["id"] = str(row.id)
            return stored

    # Lazily construct dependencies
    def _get_primary_search(self) -> WebConnector:
        if self._primary_search is None:
            if not (settings.searxng_host or settings.searx_host):
                raise ConfigurationError(
                    "SearxNG is required for company research. Set SEARXNG_HOST (or SEARX_HOST)."
                )
            self._primary_search = WebConnector(searx_k=self.search_results)
        return self._primary_search

    def _get_fallback_search(self) -> WebConnector:
        # SearxNG-only: no fallback provider.
        return self._get_primary_search()

    def _get_firecrawl(self) -> FirecrawlClient:
        if self._firecrawl is None:
            self._firecrawl = FirecrawlClient(
                base_url=settings.firecrawl_base_url,
                timeout=settings.firecrawl_timeout,
            )
        return self._firecrawl

    def _get_store(self) -> DataStoreService:
        if self._store is None:
            self._store = DataStoreService(default_collection=settings.company_research_collection)
        return self._store

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def get_cached_report(self, company: str) -> dict[str, Any] | None:
        company = (company or "").strip()
        if not company:
            return None
        try:
            cached = self._read_latest_from_db(company)
            if cached:
                return cached
        except Exception:
            logger.debug("Company research DB cache lookup failed", exc_info=True)

        # Back-compat: older deployments may have written to the JSON document store.
        legacy = self._find_latest(company)
        if legacy is None:
            return None
        try:
            legacy_payload = dict(legacy)
            legacy_payload.pop("id", None)

            generated_at: datetime | None = None
            raw_generated = legacy_payload.get("generated_at")
            if isinstance(raw_generated, str) and raw_generated.strip():
                try:
                    generated_at = datetime.fromisoformat(
                        raw_generated.strip().replace("Z", "+00:00")
                    )
                except Exception:
                    generated_at = None

            stored = self._upsert_latest_to_db(
                company=company,
                payload=legacy_payload,
                model_name=str(legacy_payload.get("model"))
                if legacy_payload.get("model")
                else None,
                generated_at=generated_at,
            )
            return stored
        except Exception:
            return legacy

    def generate_report(self, company: str, *, refresh: bool = False) -> dict[str, Any]:
        company = company.strip()
        if not company:
            raise ValueError("Company name is required")

        if not refresh:
            cached = self.get_cached_report(company)
            if cached:
                return cached

        sources, search_meta = self._collect_sources(company)
        self._ensure_llm()
        report = self._run_llm(company, sources)
        references = report.references or []
        references.extend([src.url for src in sources if src.url])
        sanitized_refs = list(dict.fromkeys([ref for ref in references if ref]))
        payload = {
            "company": company,
            "model": self._model_name,
            "generated_at": datetime.now(UTC).isoformat(),
            "report": report.dict(),
            "sources": [src.to_payload() for src in sources],
            "search": search_meta,
        }
        payload["report"]["references"] = sanitized_refs

        try:
            return self._upsert_latest_to_db(
                company=company,
                payload=payload,
                model_name=self._model_name,
                generated_at=datetime.now(UTC),
            )
        except Exception:
            logger.exception("Failed to persist company research report")
            # Fallback to the legacy JSON store so the feature still works even if the
            # relational table hasn't been migrated yet.
            self._get_store().update_one({"company": company}, {"$set": payload}, upsert=True)
            stored = self._find_latest(company)
            return stored or payload

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------
    def _ensure_llm(self) -> None:
        if self._structured_llm is not None:
            return
        api_key = settings.openai_api_key.get_secret_value() if settings.openai_api_key else None
        if not api_key:
            raise RuntimeError(
                "OpenAI not configured: set OPENAI_API_KEY to enable company research"
            )
        llm = ChatOpenAI(
            model=self._model_name,
            temperature=0.15,
            api_key=api_key,
            base_url=settings.openai_base_url,
            organization=settings.openai_organization,
        )
        self._llm = llm
        self._structured_llm = llm.with_structured_output(CompanyResearchReport)

    def _collect_sources(self, company: str) -> tuple[list[EnrichedSource], dict[str, Any]]:
        primary = self._search(company, self._get_primary_search())
        hits = primary.hits[: self.search_results]
        meta = {"provider": primary.provider, "hits": len(hits), "meta": primary.meta}
        if not hits and primary.meta and primary.meta.get("status") == "unconfigured":
            raise ConfigurationError(
                "SearxNG is required for company research. Set SEARXNG_HOST (or SEARX_HOST)."
            )

        provider = meta.get("provider")
        if not hits:
            return [], meta

        # Firecrawl requests are network-bound; parallelize for significant speedups.
        max_workers = min(8, len(hits))

        def _enrich(hit: SearchHit) -> EnrichedSource:
            return self._enrich_hit(hit, provider)

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            sources = list(executor.map(_enrich, hits))
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
        response = self._get_firecrawl().scrape(url, render_js=self._firecrawl_render_js)
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
        record = self._get_store().find_one({"company": company})
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
