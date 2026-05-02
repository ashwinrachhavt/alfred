"""Celery task: mark stale ZettelSessions as abandoned.

A session is "stale" when its ``updated_at`` is more than
``STALE_THRESHOLD_HOURS`` old AND its ``ended_at`` is still NULL.
Applying this transitions the derived status from ``active`` to
``abandoned`` (D4 -- status is derived from ``ended_at`` and
``summary_card_id``).

User impact: prevents zombie sessions from accumulating in the UI's
session stack. Cards are preserved; the user can still reopen the
session URL and see their prior work.
"""

from __future__ import annotations

import logging
from datetime import timedelta

from celery import shared_task

from alfred.core.utils import utcnow_naive

logger = logging.getLogger(__name__)

STALE_THRESHOLD_HOURS = 24


@shared_task(name="alfred.tasks.session_cleanup.abandon_stale_sessions")
def abandon_stale_sessions() -> dict[str, int]:
    """Mark active sessions idle > STALE_THRESHOLD_HOURS as abandoned.

    Returns a summary dict: ``{"abandoned_count": N}``. Callers (tests +
    beat schedule logs) can use this for visibility.
    """
    from sqlmodel import select

    from alfred.core.database import SessionLocal
    from alfred.models.zettel import ZettelSession

    cutoff = utcnow_naive() - timedelta(hours=STALE_THRESHOLD_HOURS)
    abandoned = 0
    session = SessionLocal()
    try:
        stmt = select(ZettelSession).where(
            ZettelSession.ended_at.is_(None),
            ZettelSession.updated_at < cutoff,
        )
        for zs in session.exec(stmt):
            zs.ended_at = utcnow_naive()
            # Note: we DO bump updated_at here intentionally because this IS
            # a status change (active -> abandoned). That is a legitimate
            # product-level event, unlike infrastructure writes (embedding,
            # bloom inference) where updated-at-corruption applies.
            session.add(zs)
            abandoned += 1
        session.commit()
    finally:
        session.close()

    logger.info("abandon_stale_sessions: %s sessions marked abandoned", abandoned)
    return {"abandoned_count": abandoned}


__all__ = ["STALE_THRESHOLD_HOURS", "abandon_stale_sessions"]
