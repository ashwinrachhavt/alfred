"""Today page API — serves the daily briefing."""
from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Query

from alfred.schemas.today import TodayBriefingResponse, TodayCalendarResponse

router = APIRouter(prefix="/api/today", tags=["today"])


@router.get("/briefing", response_model=TodayBriefingResponse)
def get_briefing(
    day: date | None = Query(default=None, alias="date"),
    tz: str = Query(default="UTC", min_length=1, max_length=64),
) -> TodayBriefingResponse:
    """Return a daily briefing for the requested date."""
    from alfred.tasks.daily_briefing import build_daily_briefing

    # Run synchronously for now — fast enough for single user
    return build_daily_briefing(target_date=day, tz_name=tz)


@router.get("/calendar", response_model=TodayCalendarResponse)
def get_calendar(
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    days: int = Query(default=120, ge=28, le=366),
    tz: str = Query(default="UTC", min_length=1, max_length=64),
) -> TodayCalendarResponse:
    """Return day-level activity counts for calendar auditing."""
    from alfred.tasks.daily_briefing import build_today_calendar

    return build_today_calendar(
        start_date=start_date,
        end_date=end_date,
        days=days,
        tz_name=tz,
    )
