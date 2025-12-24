from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Query, Response, status
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

from alfred.core.celery_client import get_celery_client
from alfred.core.dependencies import (
    get_company_insights_service,
    get_company_interviews_service,
    get_company_research_service,
)
from alfred.core.exceptions import ServiceUnavailableError
from alfred.schemas.company_interviews import InterviewProvider
from alfred.services.company_outreach import generate_company_outreach
from alfred.services.contact_discovery import discover_contacts

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


@router.get("/interviews")
async def company_interviews(
    response: Response,
    name: str = Query(..., description="Company name"),
    provider: str | None = Query(
        None,
        description="Optional provider filter: glassdoor | blind",
        pattern=r"^(glassdoor|blind)$",
    ),
    role: str | None = Query(None, description="Optional role filter"),
    limit: int = Query(50, ge=1, le=500),
    skip: int = Query(0, ge=0),
    refresh: bool = Query(False, description="Sync interviews before returning results"),
    background: bool = Query(False, description="Enqueue sync task instead of blocking"),
    max_items_per_provider: int = Query(
        0,
        ge=0,
        le=2000,
        description="0 means 'all available' for Glassdoor paid API; for Blind it caps results.",
    ),
):
    if not name.strip():
        raise HTTPException(status_code=422, detail="name is required")

    try:
        svc = get_company_interviews_service()

        if background:
            celery_client = get_celery_client()
            async_result = celery_client.send_task(
                "alfred.tasks.company_interviews.sync",
                kwargs={
                    "company": name,
                    "providers": [provider] if provider else None,
                    "refresh": refresh,
                    "max_items_per_provider": max_items_per_provider,
                },
            )
            response.status_code = status.HTTP_202_ACCEPTED
            return {
                "task_id": async_result.id,
                "status_url": f"/tasks/{async_result.id}",
                "status": "queued",
            }

        if refresh:
            providers = (
                (InterviewProvider(provider),)
                if provider
                else (InterviewProvider.glassdoor, InterviewProvider.blind)
            )
            await run_in_threadpool(
                svc.sync_company_interviews,
                name,
                providers=providers,
                refresh=True,
                max_items_per_provider=max_items_per_provider,
            )

        prov = InterviewProvider(provider) if provider else None
        rows = await run_in_threadpool(
            svc.list_interviews,
            company=name,
            provider=prov,
            role=role,
            limit=limit,
            skip=skip,
        )
        return {
            "company": name,
            "provider": provider,
            "role": role,
            "limit": limit,
            "skip": skip,
            "items": rows,
        }
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Company interviews failed")
        raise ServiceUnavailableError("Company interviews failed") from exc


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
):
    if not name.strip():
        raise HTTPException(status_code=422, detail="name is required")

    try:
        contacts = discover_contacts(name, limit=limit)
        if role:
            role_l = role.lower()
            contacts = [c for c in contacts if role_l in (c.get("title") or "").lower()]
        return {"company": name, "role": role, "limit": limit, "items": contacts}
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
