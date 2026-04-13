"""Streaming zettel creation orchestrator.

Saves a card immediately, then runs two concurrent async tracks:
  Track A: embedding + Qdrant sync + vector search + auto-link
  Track B: o4-mini reasoning + enrichment + decomposition + gaps

Yields SSE-formatted strings for each event.
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncGenerator, Callable
from typing import Any

from sqlmodel import Session

from alfred.api.dependencies import get_db_session
from alfred.schemas.zettel import ZettelCardCreate
from alfred.services.zettelkasten_service import ZettelkastenService

logger = logging.getLogger(__name__)


def _sse(event: str, data: dict[str, Any]) -> str:
    """Format a single SSE event."""
    return f"event: {event}\ndata: {json.dumps(data, default=str)}\n\n"


class ZettelCreationStream:
    """Orchestrates streaming zettel creation with concurrent enrichment."""

    def __init__(
        self,
        payload: ZettelCardCreate,
        db_session_factory: Callable[[], Session] | None = None,
    ) -> None:
        self.payload = payload
        self._db_factory = db_session_factory or (lambda: next(get_db_session()))
        self.card_id: int | None = None
        self._card_title: str = ""

    def _save_card_and_invalidate(self) -> dict[str, Any]:
        """Synchronous card save + cache invalidation. Runs in executor.

        Cache invalidation happens here (not Phase 2) so the card is visible
        in the UI immediately, even if the stream dies during enrichment.

        Note: session lifecycle is managed by the factory (e.g. FastAPI's
        ``get_db_session`` generator handles cleanup automatically).
        """
        session = self._db_factory()
        svc = ZettelkastenService(session)
        card = svc.create_card(**self.payload.model_dump())
        self.card_id = card.id
        self._card_title = card.title

        # Invalidate caches immediately so card appears in UI
        self._invalidate_caches()

        return {"id": card.id, "title": card.title, "status": card.status}

    def _invalidate_caches(self) -> None:
        """Invalidate topic/tag/graph caches after creation."""
        try:
            from alfred.core.redis_client import get_redis_client

            redis = get_redis_client()
            if redis:
                for prefix in ("zettel:topics:", "zettel:tags:", "zettel:graph:"):
                    for key in redis.scan_iter(f"{prefix}*"):
                        redis.delete(key)
        except Exception:
            logger.debug("Cache invalidation failed (non-fatal)", exc_info=True)

    async def run_phase0(self) -> AsyncGenerator[str, None]:
        """Phase 0: save the card to DB, invalidate caches, emit card_saved."""
        try:
            result = await asyncio.to_thread(self._save_card_and_invalidate)
            yield _sse("card_saved", result)
        except Exception as exc:
            logger.error("Phase 0 failed: %s", exc, exc_info=True)
            yield _sse("error", {"step": "card_save", "message": str(exc)})

    async def run(self) -> AsyncGenerator[str, None]:
        """Full pipeline: Phase 0 -> Phase 1 (concurrent tracks) -> Phase 2."""
        # Phase 0: save card + invalidate caches
        async for event in self.run_phase0():
            yield event

        if self.card_id is None:
            # Phase 0 failed — emit done and stop
            yield _sse("done", {"card": None, "stats": {"error": "card_save_failed"}})
            return

        # Phase 1 and 2 will be added in later tasks
        yield _sse("done", {"card": {"id": self.card_id, "title": self._card_title}, "stats": {}})
