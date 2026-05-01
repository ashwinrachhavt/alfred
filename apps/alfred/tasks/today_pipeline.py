"""Nightly Today pipeline — STUB for T9.

This module is a placeholder so the Celery worker can import it and
beat_schedule can reference its task. The real implementation lands in
T10 (pipeline framework), T11 (digest + carry-over agents), and T12
(full task body + trigger endpoint + UI).

Do NOT add real logic here in T9.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta, tzinfo
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from celery import shared_task


@shared_task(name="alfred.tasks.today_pipeline.run_for_yesterday")
def run_for_yesterday(tz_name: str = "UTC") -> dict:
    """Resolve yesterday in the user's tz and dispatch pipeline. STUB."""
    # T12 replaces this body.
    tz: tzinfo
    try:
        tz = ZoneInfo(tz_name)
    except ZoneInfoNotFoundError:
        tz = UTC
    now_local = datetime.now(tz)
    yesterday = (now_local.date() - timedelta(days=1)).isoformat()
    return {"status": "stub", "would_process_date": yesterday, "tz": tz_name}


@shared_task(name="alfred.tasks.today_pipeline.run_for_date")
def run_for_date(entry_date: str, tz_name: str = "UTC") -> dict:
    """Dispatch pipeline for an explicit date. STUB."""
    # T12 replaces this body.
    return {"status": "stub", "date": entry_date, "tz": tz_name}
