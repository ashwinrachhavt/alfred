from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Query, Response, status
from pydantic import BaseModel, EmailStr, Field
from starlette.concurrency import run_in_threadpool

from alfred.core.celery_client import get_celery_client
from alfred.core.dependencies import (
    get_company_insights_service,
    get_company_research_service,
)
from alfred.core.exceptions import ServiceUnavailableError
from alfred.services.company_outreach import generate_company_outreach
from alfred.services.outreach_service import OutreachService

router = APIRouter(prefix="/company", tags=["company"])
logger = logging.getLogger(__name__)


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


@router.get("/insights")
async def company_insights(
    response: Response,
    name: str = Query(..., description="Company name"),
    role: str | None = Query(None, description="Role for compensation queries (recommended)"),
    refresh: bool = Query(False, description="Force a new fetch + regeneration"),
    background: bool = Query(False, description="Enqueue a background task instead of blocking"),
):
    if not name.strip():
        raise HTTPException(status_code=422, detail="name is required")

    try:
        service = get_company_insights_service()

        if background:
            if not refresh:
                cached = service.get_cached_report(name)
                if cached:
                    return cached

            celery_client = get_celery_client()
            async_result = celery_client.send_task(
                "alfred.tasks.company_insights.generate",
                kwargs={"company": name, "role": role, "refresh": refresh},
            )
            response.status_code = status.HTTP_202_ACCEPTED
            return {
                "task_id": async_result.id,
                "status_url": f"/tasks/{async_result.id}",
                "status": "queued",
            }

        return await run_in_threadpool(service.generate_report, name, role=role, refresh=refresh)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Company insights failed")
        raise ServiceUnavailableError("Company insights failed") from exc


@router.get("/outreach")
async def company_outreach(
    name: str = Query(..., description="Company name"),
    role: str = Query("AI Engineer", description="Target role or angle for the outreach"),
):
    if not name.strip():
        raise HTTPException(status_code=422, detail="name is required")

    try:
        payload = await run_in_threadpool(generate_company_outreach, company=name, role=role)
        return {"company": name, "role": role, **payload}
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Company outreach failed")
        raise ServiceUnavailableError("Company outreach failed") from exc


@router.get("/contacts")
async def company_contacts(
    name: str = Query(..., description="Company name"),
    role: str | None = Query(None, description="Optional role/title filter, e.g. 'engineering'"),
    limit: int = Query(20, ge=1, le=50, description="Max contacts to return"),
    refresh: bool = Query(False, description="Force refresh from providers and bypass cache"),
):
    if not name.strip():
        raise HTTPException(status_code=422, detail="name is required")

    try:
        contacts = OutreachService().list_contacts(
            name, limit=limit, role_filter=role, refresh=refresh
        )
        return {
            "company": name,
            "role": role,
            "limit": limit,
            "refresh": refresh,
            "items": contacts,
        }
    except Exception as exc:
        logger.exception("Company contacts lookup failed")
        raise ServiceUnavailableError("Company contacts lookup failed") from exc


class OutreachRequest(BaseModel):
    name: str = Field(..., description="Company name")
    role: str | None = Field("AI Engineer", description="Target role or outreach angle")
    context: str | None = Field(
        None,
        description="Optional extra context or instructions to personalize the outreach output.",
    )
    k: int | None = Field(
        None, description="Optional top-k documents to retrieve from the personal knowledge base"
    )


@router.post("/outreach")
async def company_outreach_post(payload: OutreachRequest):
    if not (payload.name or "").strip():
        raise HTTPException(status_code=422, detail="name is required")

    try:
        data = await run_in_threadpool(
            generate_company_outreach,
            company=payload.name,
            role=payload.role or "AI Engineer",
            personal_context=payload.context or "",
            k=payload.k or 6,
        )
        return {"company": payload.name, "role": payload.role or "AI Engineer", **data}
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Company outreach failed")
        raise ServiceUnavailableError("Company outreach failed") from exc


class OutreachSendRequest(BaseModel):
    company: str = Field(..., description="Company name")
    contact_email: EmailStr
    contact_name: str | None = Field(default=None)
    contact_title: str | None = Field(default=None)
    subject: str = Field(..., description="Email subject")
    body: str = Field(..., description="Plaintext email body")
    dry_run: bool = Field(default=False, description="If true, do not send; just log")


@router.post("/outreach/send")
async def send_outreach_email(payload: OutreachSendRequest):
    if not payload.company.strip():
        raise HTTPException(status_code=422, detail="company is required")
    try:
        svc = OutreachService()
        message = await run_in_threadpool(
            svc.send_email,
            company=payload.company,
            contact_email=str(payload.contact_email),
            contact_name=payload.contact_name or "",
            contact_title=payload.contact_title or "",
            subject=payload.subject,
            body=payload.body,
            dry_run=payload.dry_run,
        )
        return {
            "id": str(message.id),
            "status": message.status,
            "sent_at": message.sent_at,
            "provider": message.provider,
            "dry_run": payload.dry_run,
        }
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Company outreach send failed")
        raise ServiceUnavailableError("Company outreach send failed") from exc
