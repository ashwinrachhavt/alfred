from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from alfred.core import agno_tracing
from alfred.services.tools.web_tools import render_web_search_markdown
from alfred.services.tools.wiki_tools import render_wiki_lookup_markdown

router = APIRouter(prefix="/api/agents", tags=["agents"])
logger = logging.getLogger(__name__)


class DemoRequest(BaseModel):
    query: str = Field(..., description="Topic or query to search")
    max_results: int = Field(5, ge=1, le=10)
    top_k: int = Field(2, ge=1, le=10)


@router.post("/demo")
def demo_run(payload: DemoRequest) -> dict[str, Any]:
    """Run a small end-to-end demo using tools with tracing enabled if configured."""
    agno_tracing.init()
    q = payload.query
    try:
        with agno_tracing.agent_run(
            "DemoAgent", {"query": q, "max_results": payload.max_results, "top_k": payload.top_k}
        ):
            web_md = render_web_search_markdown(q, max_results=payload.max_results)
            wiki_md = render_wiki_lookup_markdown(q, top_k=payload.top_k)
            agno_tracing.log_output({"web": bool(web_md), "wiki": bool(wiki_md)})
            return {
                "trace_enabled": agno_tracing.is_enabled(),
                "query": q,
                "web_markdown": web_md,
                "wiki_markdown": wiki_md,
            }
    except Exception as exc:
        logger.warning("Demo agent run failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))
