"""Nightly Today pipeline — real task bodies (T12).

``run_for_yesterday`` computes "yesterday in tz_name" and dispatches the
:class:`DailyPipeline`. ``run_for_date`` is the explicit-date variant for
manual triggers and replays.

Both wrap the pipeline in a Redis ``SET NX`` lock keyed on
``(entry_date, user_id)`` so that concurrent runs (beat + manual trigger
race) cannot clobber each other. If Redis is unavailable (the helper
returns ``None``), the lock gracefully no-ops and the pipeline still
runs.

The public task names match the beat schedule in ``alfred.core.celery``
— do NOT rename them.
"""

from __future__ import annotations

import logging
from datetime import UTC, date, datetime, timedelta, tzinfo
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from celery import shared_task

from alfred.core.database import get_session
from alfred.core.redis_client import get_redis_client
from alfred.services.today.pipeline import DailyPipeline

log = logging.getLogger(__name__)

# Lock TTL slightly longer than the longest pipeline run we expect, so
# a crashed worker releases the slot automatically.
_LOCK_TTL_SECONDS = 600


def _yesterday_in_tz(tz_name: str) -> date:
    tz: tzinfo
    try:
        tz = ZoneInfo(tz_name)
    except ZoneInfoNotFoundError:
        tz = UTC
    today_local = datetime.now(tz).date()
    return today_local - timedelta(days=1)


def _run(entry_date: date, tz_name: str, user_id: str | None = None) -> dict:
    """Shared helper — runs the pipeline under a Redis lock.

    Returns a summary dict describing the run. If the lock is held, the
    status is ``"locked"`` and the pipeline is not invoked.
    """
    lock_key = f"daily_pipeline:{entry_date.isoformat()}:{user_id or 'default'}"

    redis_client = get_redis_client()
    # ``SET NX EX`` — fail fast if another run is in-flight. If redis is
    # unavailable the helper returns ``None``; we fall through unlocked.
    acquired = True
    if redis_client is not None:
        try:
            acquired = bool(
                redis_client.set(lock_key, "1", nx=True, ex=_LOCK_TTL_SECONDS),
            )
        except Exception:
            # Redis is reachable-ish but the command failed; proceed
            # without the lock rather than wedging the pipeline.
            log.exception("failed to acquire pipeline lock %s", lock_key)
            acquired = True
            redis_client = None

    if not acquired:
        log.warning("today pipeline locked: %s", lock_key)
        return {"status": "locked", "date": entry_date.isoformat(), "tz": tz_name}

    try:
        # ``get_session`` yields a request-scoped session. Celery tasks
        # mirror the FastAPI dependency pattern via ``next(generator)``.
        session_gen = get_session()
        session = next(session_gen)
        try:
            reflection = DailyPipeline().run(
                session=session,
                entry_date=entry_date,
                tz_name=tz_name,
                user_id=user_id,
            )
        finally:
            session.close()

        return {
            "status": "ok",
            "date": entry_date.isoformat(),
            "tz": tz_name,
            "reflection_id": reflection.id,
            "run_id": reflection.pipeline_run_id,
            "stages_ran": list(reflection.stages_ran),
        }
    finally:
        if redis_client is not None:
            try:
                redis_client.delete(lock_key)
            except Exception:
                log.exception("failed to release pipeline lock %s", lock_key)


@shared_task(name="alfred.tasks.today_pipeline.run_for_yesterday")
def run_for_yesterday(tz_name: str = "UTC", user_id: str | None = None) -> dict:
    """Called by Celery beat at the nightly UTC hour."""
    entry_date = _yesterday_in_tz(tz_name)
    log.info("today pipeline run_for_yesterday date=%s tz=%s", entry_date, tz_name)
    return _run(entry_date, tz_name, user_id)


@shared_task(name="alfred.tasks.today_pipeline.run_for_date")
def run_for_date(entry_date: str, tz_name: str = "UTC", user_id: str | None = None) -> dict:
    """Explicit-date dispatch for manual trigger / replay."""
    target = date.fromisoformat(entry_date)
    log.info("today pipeline run_for_date date=%s tz=%s", target, tz_name)
    return _run(target, tz_name, user_id)
