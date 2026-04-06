"""Today page API — serves the daily briefing."""
from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(prefix="/api/today", tags=["today"])


@router.get("/briefing")
def get_briefing() -> dict:
    """Return today's briefing. Computes live (no cached briefing row yet)."""
    from alfred.tasks.daily_briefing import generate_daily_briefing

    # Run synchronously for now — fast enough for single user
    return generate_daily_briefing()
