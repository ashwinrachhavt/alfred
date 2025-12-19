from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from alfred.core.exceptions import ServiceUnavailableError
from alfred.services.research import run_research

router = APIRouter(prefix="/research", tags=["research"])
logger = logging.getLogger(__name__)


class ResearchRequest(BaseModel):
    query: str = Field(..., min_length=5, description="Primary research question")
    target_length_words: int = Field(
        default=1000,
        ge=300,
        le=3000,
        description="Desired length of the final article",
    )
    tone: str = Field(
        default="neutral",
        description="Article tone (neutral, casual, technical)",
    )


class ResearchResponse(BaseModel):
    article: str
    state: dict[str, object]


@router.post("/deep", response_model=ResearchResponse)
async def deep_research_endpoint(payload: ResearchRequest) -> ResearchResponse:
    try:
        article, state = await run_research(
            query=payload.query,
            target_length_words=payload.target_length_words,
            tone=payload.tone,
        )
    except Exception as exc:  # pragma: no cover - surface orchestration issues
        logger.exception("Research pipeline failed")
        raise ServiceUnavailableError("Research pipeline failed") from exc

    if not article:
        raise HTTPException(status_code=500, detail="Research pipeline returned no article")

    return ResearchResponse(article=article, state=state)
