from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Query, Response, status
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

from alfred.core.celery_client import get_celery_client
from alfred.core.dependencies import get_company_research_service
from alfred.core.exceptions import ServiceUnavailableError
from alfred.services.company_outreach import generate_company_outreach

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
