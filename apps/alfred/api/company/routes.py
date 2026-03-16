from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, HTTPException, Query, Response, status
from pydantic import BaseModel
from sqlalchemy.exc import ProgrammingError
from sqlmodel import select
from starlette.concurrency import run_in_threadpool

from alfred.core.celery_client import get_celery_client
from alfred.core.database import SessionLocal
from alfred.core.dependencies import get_company_research_service
from alfred.core.exceptions import ServiceUnavailableError
from alfred.models.company import CompanyResearchReportRow

router = APIRouter(prefix="/company", tags=["company"])
logger = logging.getLogger(__name__)


class CompanyResearchReportSummary(BaseModel):
    id: str
    company: str
    model_name: str | None = None
    generated_at: str | None = None
    updated_at: str | None = None
    executive_summary: str | None = None


@router.get("/research-reports/recent", response_model=list[CompanyResearchReportSummary])
def recent_company_research_reports(
    limit: int = Query(20, ge=1, le=100, description="Number of reports to return"),
) -> list[CompanyResearchReportSummary]:
    """Return the most recently updated company research reports."""

    try:
        with SessionLocal() as session:
            rows = session.exec(
                select(CompanyResearchReportRow)
                .order_by(CompanyResearchReportRow.updated_at.desc())
                .limit(limit)
            ).all()
    except ProgrammingError as exc:
        if "company_research_reports" in str(exc):
            raise HTTPException(
                status_code=503,
                detail=(
                    "Database schema is missing `company_research_reports`. "
                    "Run migrations (e.g. `make alembic-upgrade DATABASE_URL=...`)."
                ),
            ) from exc
        raise

    results: list[CompanyResearchReportSummary] = []
    for row in rows:
        payload = row.payload or {}
        report = payload.get("report") if isinstance(payload, dict) else None
        executive_summary = None
        if isinstance(report, dict):
            summary = report.get("executive_summary")
            if isinstance(summary, str):
                executive_summary = summary

        results.append(
            CompanyResearchReportSummary(
                id=str(row.id),
                company=row.company,
                model_name=row.model_name,
                generated_at=row.generated_at.isoformat() if row.generated_at else None,
                updated_at=row.updated_at.isoformat() if row.updated_at else None,
                executive_summary=executive_summary,
            )
        )

    return results


@router.get("/research-reports/{report_id}")
def get_company_research_report(report_id: uuid.UUID) -> dict:
    """Fetch a previously saved company research report by id."""

    try:
        with SessionLocal() as session:
            row = session.get(CompanyResearchReportRow, report_id)
            if row is None:
                raise HTTPException(status_code=404, detail="company research report not found")
            payload = dict(row.payload or {})
            payload.setdefault("company", row.company)
            payload["id"] = str(row.id)
            return payload
    except ProgrammingError as exc:
        if "company_research_reports" in str(exc):
            raise HTTPException(
                status_code=503,
                detail=(
                    "Database schema is missing `company_research_reports`. "
                    "Run migrations (e.g. `make alembic-upgrade DATABASE_URL=...`)."
                ),
            ) from exc
        raise


@router.get("/research")
async def company_research(
    response: Response,
    name: str = Query(..., description="Company name"),
    refresh: bool = Query(False, description="Force a new crawl + regeneration"),
    background: bool = Query(False, description="Enqueue a background task instead of blocking"),
):
    if not name.strip():
        raise HTTPException(status_code=422, detail="name is required")

    try:
        service = get_company_research_service()

        if background:
            if not refresh:
                cached = service.get_cached_report(name)
                if cached:
                    return cached

            celery_client = get_celery_client()
            async_result = celery_client.send_task(
                "alfred.tasks.company_research.generate",
                kwargs={"company": name, "refresh": refresh},
            )
            response.status_code = status.HTTP_202_ACCEPTED
            return {
                "task_id": async_result.id,
                "status_url": f"/tasks/{async_result.id}",
                "status": "queued",
            }

        # Offload blocking work to a threadpool to keep the event loop responsive.
        return await run_in_threadpool(service.generate_report, name, refresh=refresh)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Company research failed")
        raise ServiceUnavailableError("Company research failed") from exc
