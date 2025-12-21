from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Iterable

from pymongo import UpdateOne
from pymongo.collection import Collection
from pymongo.database import Database

from alfred.core.exceptions import ConfigurationError, ServiceUnavailableError
from alfred.core.settings import settings
from alfred.schemas.company_interviews import (
    CompanyInterviewExperience,
    InterviewProvider,
    InterviewSyncSummary,
)

logger = logging.getLogger(__name__)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _compact(text: str | None) -> str:
    return " ".join((text or "").split()).strip()


def _fingerprint(*parts: str) -> str:
    h = hashlib.sha256()
    for p in parts:
        h.update(p.encode("utf-8", errors="ignore"))
        h.update(b"\x1f")
    return h.hexdigest()


def _source_id(
    provider: InterviewProvider, *, source_url: str | None, company: str, raw: dict[str, Any]
) -> str:
    if source_url and source_url.strip():
        return f"{provider.value}|{source_url.strip()}"

    # Fallback: stable hash from a few common fields.
    base = raw.get("upstream") if isinstance(raw.get("upstream"), dict) else raw
    role = _compact(str(base.get("job_title") or base.get("jobTitle") or base.get("role") or ""))
    when = _compact(
        str(base.get("date") or base.get("interview_date") or base.get("created_at") or "")
    )
    summary = _compact(
        str(base.get("process_summary") or base.get("summary") or base.get("process") or "")
    )
    return f"{provider.value}|hash:{_fingerprint(company.strip(), role, when, summary)}"


@dataclass
class CompanyInterviewsService:
    """Interview-focused collector + storage layer.

    Stores each interview experience as an individual Mongo document so we can:
    - Incrementally sync new experiences
    - Query/paginate by role/location/date/provider
    - Run downstream red-flag/culture-fit analyses efficiently

    Provider strategies:
    - Glassdoor: OpenWeb Ninja paid API (best fidelity, supports pagination).
    - Blind: public-only via web search + Firecrawl (best-effort, may be gated).
    """

    database: Database | None = None
    collection_name: str = settings.company_interviews_collection
    glassdoor_service: Any | None = None
    blind_service: Any | None = None

    def __post_init__(self) -> None:
        if self.database is None:
            from alfred.connectors.mongo_connector import MongoConnector

            self.database = MongoConnector().database
        self._collection: Collection = self.database.get_collection(self.collection_name)

        if self.glassdoor_service is None:
            from alfred.services.glassdoor_service import GlassdoorService

            self.glassdoor_service = GlassdoorService()
        if self.blind_service is None:
            from alfred.connectors.firecrawl_connector import FirecrawlClient
            from alfred.connectors.web_connector import WebConnector
            from alfred.services.blind_service import BlindService

            mode = "searx" if (settings.searxng_host or settings.searx_host) else "multi"
            web = WebConnector(mode=mode, searx_k=10)
            firecrawl = FirecrawlClient(
                base_url=settings.firecrawl_base_url,
                timeout=settings.firecrawl_timeout,
            )
            self.blind_service = BlindService(web=web, firecrawl=firecrawl, max_hits=10)

    # -----------------
    # Indexes
    # -----------------
    def ensure_indexes(self) -> None:
        """Create best-effort indexes for interview experience queries."""
        try:
            self._collection.create_index([("company", 1)], name="company")
            self._collection.create_index([("provider", 1)], name="provider")
            self._collection.create_index(
                [("company", 1), ("provider", 1)], name="company_provider"
            )
            self._collection.create_index([("company", 1), ("role", 1)], name="company_role")
            self._collection.create_index(
                [("company", 1), ("updated_at", -1)], name="company_updated_desc"
            )
            self._collection.create_index([("source_id", 1)], name="source_id_unique", unique=True)
        except Exception:
            pass

    # -----------------
    # Read API
    # -----------------
    def list_interviews(
        self,
        *,
        company: str,
        provider: InterviewProvider | None = None,
        role: str | None = None,
        limit: int = 50,
        skip: int = 0,
    ) -> list[dict[str, Any]]:
        filt: dict[str, Any] = {"company": company}
        if provider is not None:
            filt["provider"] = provider.value
        if role and role.strip():
            filt["role"] = role.strip()

        cursor = (
            self._collection.find(filt, {"raw": 0})
            .sort([("updated_at", -1)])
            .skip(max(0, int(skip)))
            .limit(max(1, min(int(limit), 500)))
        )
        return list(cursor)

    # -----------------
    # Sync / ingest
    # -----------------
    def sync_company_interviews(
        self,
        company: str,
        *,
        providers: Iterable[InterviewProvider] = (
            InterviewProvider.glassdoor,
            InterviewProvider.blind,
        ),
        refresh: bool = False,
        max_items_per_provider: int = 0,
    ) -> InterviewSyncSummary:
        company = (company or "").strip()
        if not company:
            raise ValueError("company is required")

        summary = InterviewSyncSummary(company=company, providers=list(providers))
        ops: list[UpdateOne] = []
        now = _utcnow()

        for provider in providers:
            if provider == InterviewProvider.glassdoor:
                ops.extend(
                    self._collect_glassdoor(
                        company, now=now, refresh=refresh, max_items=max_items_per_provider
                    )
                )
            elif provider == InterviewProvider.blind:
                ops.extend(self._collect_blind(company, now=now, max_items=max_items_per_provider))
            else:
                summary.warnings.append(f"Unsupported provider: {provider.value}")

        if not ops:
            summary.warnings.append("No interview experiences found.")
            return summary

        try:
            res = self._collection.bulk_write(ops, ordered=False)
            summary.inserted = int(getattr(res, "upserted_count", 0) or 0)
            summary.updated = int(getattr(res, "modified_count", 0) or 0)
            summary.total_seen = len(ops)
            return summary
        except Exception as exc:
            raise ServiceUnavailableError(
                f"Failed to persist interview experiences: {exc}"
            ) from exc

    def _collect_glassdoor(
        self,
        company: str,
        *,
        now: datetime,
        refresh: bool,
        max_items: int,
    ) -> list[UpdateOne]:
        try:
            # max_items=0 -> fetch all available from the paid API (may be large).
            max_interviews = int(max_items) if int(max_items) > 0 else 0
            items = self.glassdoor_service.get_interview_experiences_with_raw_sync(
                company, max_interviews=max_interviews
            )
        except ConfigurationError as exc:
            logger.info("Glassdoor not configured: %s", exc)
            return []
        except Exception as exc:
            logger.info("Glassdoor interview fetch failed: %s", exc)
            return []

        ops: list[UpdateOne] = []
        for i, raw_upstream in items:
            raw = {"normalized": i.model_dump(mode="json"), "upstream": raw_upstream}
            source_url = i.source_url
            sid = _source_id(
                InterviewProvider.glassdoor, source_url=source_url, company=company, raw=raw
            )
            doc = CompanyInterviewExperience(
                company=company,
                provider=InterviewProvider.glassdoor,
                source_id=sid,
                source_url=source_url,
                source_title=None,
                role=i.role,
                location=i.location,
                interview_date=i.interview_date,
                difficulty=i.difficulty,
                outcome=i.outcome,
                process_summary=i.process_summary,
                questions=i.questions,
                raw=raw,
            ).model_dump(mode="json")
            doc["provider"] = InterviewProvider.glassdoor.value
            doc["last_seen_at"] = now
            doc["updated_at"] = now

            update = {"$set": doc, "$setOnInsert": {"created_at": now, "ingested_at": now}}
            ops.append(UpdateOne({"source_id": sid}, update, upsert=True))

        return ops

    def _collect_blind(self, company: str, *, now: datetime, max_items: int) -> list[UpdateOne]:
        try:
            interviews, sources = self.blind_service.search_interview_posts_sync(company)
        except Exception as exc:
            logger.info("Blind interview fetch failed: %s", exc)
            return []

        if max_items and max_items > 0:
            interviews = interviews[: int(max_items)]

        ops: list[UpdateOne] = []
        title_by_url: dict[str, str] = {
            (s.url or ""): (s.title or "") for s in sources if getattr(s, "url", None)
        }
        for i in interviews:
            raw = i.model_dump(mode="json")
            source_url = i.source_url
            sid = _source_id(
                InterviewProvider.blind, source_url=source_url, company=company, raw=raw
            )
            doc = CompanyInterviewExperience(
                company=company,
                provider=InterviewProvider.blind,
                source_id=sid,
                source_url=source_url,
                source_title=title_by_url.get(source_url or "") or None,
                role=i.role,
                location=i.location,
                interview_date=i.interview_date,
                difficulty=i.difficulty,
                outcome=i.outcome,
                process_summary=i.process_summary,
                questions=i.questions,
                raw=raw,
            ).model_dump(mode="json")
            doc["provider"] = InterviewProvider.blind.value
            doc["last_seen_at"] = now
            doc["updated_at"] = now

            update = {"$set": doc, "$setOnInsert": {"created_at": now, "ingested_at": now}}
            ops.append(UpdateOne({"source_id": sid}, update, upsert=True))

        return ops
