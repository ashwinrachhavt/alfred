from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Iterable

from sqlalchemy import select
from sqlmodel import Session

from alfred.core.database import SessionLocal
from alfred.core.exceptions import ConfigurationError
from alfred.core.settings import settings
from alfred.models.company import CompanyInterviewRow
from alfred.schemas.company_interviews import (
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
    """Collects and stores interview experiences in Postgres."""

    glassdoor_service: Any | None = None
    blind_service: Any | None = None
    session: Session | None = None

    def __post_init__(self) -> None:
        if self.session is None:
            self.session = SessionLocal()

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

    def ensure_indexes(self) -> None:
        return

    def sync_company_interviews(
        self,
        company: str,
        *,
        providers: Iterable[InterviewProvider],
        refresh: bool,
        max_items_per_provider: int = 0,
    ) -> InterviewSyncSummary:
        company = (company or "").strip()
        if not company:
            raise ValueError("company is required")

        summary = InterviewSyncSummary(company=company, providers=list(providers))
        ops: list[dict[str, Any]] = []
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

        inserted = 0
        updated = 0
        with self.session as s:
            for op in ops:
                filt = op["filter"]
                data = op["data"]
                sid = filt["source_id"]
                row = s.exec(
                    select(CompanyInterviewRow).where(CompanyInterviewRow.source_id == sid)
                ).first()
                if row is None:
                    s.add(data)
                    inserted += 1
                else:
                    for attr, val in data.__dict__.items():
                        if attr in {"id", "created_at"}:
                            continue
                        setattr(row, attr, val)
                    updated += 1
            s.commit()

        summary.inserted = inserted
        summary.updated = updated
        summary.total_seen = len(ops)
        return summary

    def list_interviews(
        self,
        *,
        company: str,
        provider: InterviewProvider | None = None,
        role: str | None = None,
        limit: int = 50,
        skip: int = 0,
    ) -> list[dict[str, Any]]:
        company = (company or "").strip()
        if not company:
            raise ValueError("company is required")

        with self.session as s:
            stmt = select(CompanyInterviewRow).where(CompanyInterviewRow.company == company)
            if provider:
                stmt = stmt.where(CompanyInterviewRow.provider == provider.value)
            if role:
                stmt = stmt.where(CompanyInterviewRow.role == role)
            stmt = stmt.order_by(CompanyInterviewRow.updated_at.desc())
            stmt = stmt.offset(int(max(0, skip))).limit(int(max(1, min(limit, 500))))
            rows = s.exec(stmt).all()
            return [self._serialize_row(r) for r in rows]

    # -----------------
    # Providers
    # -----------------
    def _collect_glassdoor(
        self,
        company: str,
        *,
        now: datetime,
        refresh: bool,
        max_items: int,
    ) -> list[dict[str, Any]]:
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

        ops: list[dict[str, Any]] = []
        for i, raw_upstream in items:
            raw = {"normalized": i.model_dump(mode="json"), "upstream": raw_upstream}
            source_url = i.source_url
            sid = _source_id(
                InterviewProvider.glassdoor, source_url=source_url, company=company, raw=raw
            )
            data = CompanyInterviewRow(
                company=company,
                provider=InterviewProvider.glassdoor.value,
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
                created_at=now,
                updated_at=now,
            )
            ops.append(
                {
                    "filter": {
                        "source_id": sid,
                        "company": company,
                        "provider": InterviewProvider.glassdoor.value,
                    },
                    "data": data,
                }
            )

        return ops

    def _collect_blind(
        self, company: str, *, now: datetime, max_items: int
    ) -> list[dict[str, Any]]:
        try:
            interviews, sources = self.blind_service.search_interview_posts_sync(company)
        except Exception as exc:
            logger.info("Blind interview fetch failed: %s", exc)
            return []

        if max_items and max_items > 0:
            interviews = interviews[: int(max_items)]

        ops: list[dict[str, Any]] = []
        title_by_url: dict[str, str] = {
            (s.url or ""): (s.title or "") for s in sources if getattr(s, "url", None)
        }
        for i in interviews:
            raw = i.model_dump(mode="json")
            source_url = i.source_url
            sid = _source_id(
                InterviewProvider.blind, source_url=source_url, company=company, raw=raw
            )
            data = CompanyInterviewRow(
                company=company,
                provider=InterviewProvider.blind.value,
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
                created_at=now,
                updated_at=now,
            )
            ops.append(
                {
                    "filter": {
                        "source_id": sid,
                        "company": company,
                        "provider": InterviewProvider.blind.value,
                    },
                    "data": data,
                }
            )

        return ops

    # -----------------
    # Helpers
    # -----------------
    def _serialize_row(self, row: CompanyInterviewRow) -> dict[str, Any]:
        return {
            "id": str(row.id),
            "company": row.company,
            "provider": row.provider,
            "source_id": row.source_id,
            "source_url": row.source_url,
            "source_title": row.source_title,
            "role": row.role,
            "location": row.location,
            "interview_date": row.interview_date,
            "difficulty": row.difficulty,
            "outcome": row.outcome,
            "process_summary": row.process_summary,
            "questions": row.questions,
            "updated_at": row.updated_at,
        }


__all__ = ["CompanyInterviewsService"]
