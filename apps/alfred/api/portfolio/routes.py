from __future__ import annotations

import logging

from fastapi import APIRouter, Query
from fastapi.responses import HTMLResponse
from starlette.concurrency import run_in_threadpool

from alfred.core.exceptions import ServiceUnavailableError
from alfred.services.personal_brand import get_portfolio_html

router = APIRouter(tags=["portfolio"])
logger = logging.getLogger(__name__)


@router.get("/ai", response_class=HTMLResponse)
async def portfolio_root(
    refresh: bool = Query(False, description="Regenerate the portfolio HTML (bypass cache)"),
) -> HTMLResponse:
    try:
        html = await run_in_threadpool(get_portfolio_html, refresh=refresh)
        return HTMLResponse(content=html)
    except Exception as exc:
        logger.exception("Portfolio page failed")
        raise ServiceUnavailableError("Portfolio page failed") from exc
