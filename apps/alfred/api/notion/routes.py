from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Query

from alfred.core.exceptions import ServiceUnavailableError
from alfred.services import notion

router = APIRouter(prefix="/api/notion", tags=["notion"])
logger = logging.getLogger(__name__)


@router.get("/history", response_model=dict[str, Any])
async def get_notion_history(
    start_date: Optional[str] = Query(
        default=None,
        description="ISO 8601 date string; include pages edited on/after this value.",
    ),
    end_date: Optional[str] = Query(
        default=None,
        description="ISO 8601 date string; include pages edited on/before this value.",
    ),
    limit: Optional[int] = Query(
        default=10,
        ge=1,
        le=200,
        description="Maximum number of pages to return (default 10).",
    ),
    include_content: bool = Query(
        default=False,
        description="When true, fetch full block content for each page (slower).",
    ),
) -> Dict[str, Any]:
    try:
        pages = await notion.fetch_page_history(
            start_date=start_date,
            end_date=end_date,
            limit=limit,
            include_content=include_content,
        )
        return {"success": True, "count": len(pages), "pages": pages}
    except HTTPException as http_exc:
        raise http_exc
    except RuntimeError as rt_exc:
        logger.exception("Notion dependency failed")
        raise ServiceUnavailableError("Notion service unavailable") from rt_exc
    except Exception as exc:  # pragma: no cover - unexpected runtime errors
        logger.exception("Notion history failed")
        raise ServiceUnavailableError("Notion history failed") from exc
