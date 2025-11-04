"""HTTP endpoints for generating the Bruce Wayne Daily Brief."""

from __future__ import annotations

from datetime import date
from typing import List

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from alfred.services.daily_brief import DailyBrief, generate_daily_brief

router = APIRouter(prefix="/api", tags=["daily_brief"])


class DailyBriefRequest(BaseModel):
    """Request payload for generating a daily brief."""

    user_id: str = Field(..., description="Unique identifier for the requesting user")


class DailyBriefResponse(BaseModel):
    """Response payload returned to the client UI."""

    date: str
    summary: str
    recent_highlights: List[str]
    top_priorities: List[str]
    content_idea: str
    reflection_question: str


@router.post("/daily-brief", response_model=DailyBriefResponse)
async def post_daily_brief(body: DailyBriefRequest) -> DailyBriefResponse:
    """Generate the Bruce Wayne Daily Brief for the specified user."""

    try:
        brief: DailyBrief = generate_daily_brief(body.user_id)
    except Exception as exc:  # pragma: no cover - propagate friendly error downstream
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return DailyBriefResponse(
        date=brief.date.isoformat(),
        summary=brief.summary,
        recent_highlights=brief.recent_highlights,
        top_priorities=brief.top_priorities,
        content_idea=brief.content_idea,
        reflection_question=brief.reflection_question,
    )
