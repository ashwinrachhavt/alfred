from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import HTMLResponse
from starlette.concurrency import run_in_threadpool

from alfred.core.exceptions import ServiceUnavailableError
from alfred.schemas.brand import (
    ExperienceInventory,
    InventoryRequest,
    OutreachRequest,
    OutreachResponse,
    StoriesRequest,
    StoriesResponse,
)
from alfred.services.personal_brand import (
    build_experience_inventory,
    generate_outreach,
    generate_star_stories,
    get_portfolio_html,
)

router = APIRouter(prefix="/api/brand", tags=["brand"])
logger = logging.getLogger(__name__)


@router.post("/inventory", response_model=ExperienceInventory)
async def inventory(payload: InventoryRequest) -> ExperienceInventory:
    try:
        return await run_in_threadpool(build_experience_inventory, payload)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Brand inventory failed")
        raise ServiceUnavailableError("Brand inventory failed") from exc


@router.post("/stories", response_model=StoriesResponse)
async def stories(payload: StoriesRequest) -> StoriesResponse:
    try:
        return await run_in_threadpool(generate_star_stories, payload)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Brand stories failed")
        raise ServiceUnavailableError("Brand stories failed") from exc


@router.post("/outreach", response_model=OutreachResponse)
async def outreach(payload: OutreachRequest) -> OutreachResponse:
    try:
        return await run_in_threadpool(generate_outreach, payload)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Brand outreach failed")
        raise ServiceUnavailableError("Brand outreach failed") from exc


@router.get("/portfolio/ai", response_class=HTMLResponse)
async def portfolio_ai(
    refresh: bool = Query(False, description="Regenerate the portfolio HTML (bypass cache)"),
) -> HTMLResponse:
    try:
        html = await run_in_threadpool(get_portfolio_html, refresh=refresh)
        return HTMLResponse(content=html)
    except Exception as exc:
        logger.exception("Portfolio generation failed")
        raise ServiceUnavailableError("Portfolio generation failed") from exc
