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


AUTO_LINK_THRESHOLD = 0.75


class ZettelCreationStream:
    """Orchestrates streaming zettel creation with concurrent enrichment."""

    def __init__(
        self,
        payload: ZettelCardCreate,
        db_session_factory: Callable[[], Session] | None = None,
    ) -> None:
        self.payload = payload
        self._uses_default_factory = db_session_factory is None
        if self._uses_default_factory:
            self._db_factory = self._default_session_factory
        else:
            self._db_factory = db_session_factory
        self.card_id: int | None = None
        self._card_title: str = ""

    @staticmethod
    def _default_session_factory() -> Session:
        """Create and return a fresh DB session.

        Caller is responsible for closing the session.
        """
        return next(get_db_session())

    def _save_card_and_invalidate(self) -> dict[str, Any]:
        """Synchronous card save + cache invalidation. Runs in executor.

        Cache invalidation happens here (not Phase 2) so the card is visible
        in the UI immediately, even if the stream dies during enrichment.

        Sessions created from the default factory are properly closed via
        finally. Injected sessions (e.g., in tests) are managed by the caller.
        """
        session = self._db_factory()
        try:
            svc = ZettelkastenService(session)
            card = svc.create_card(**self.payload.model_dump())
            self.card_id = card.id
            self._card_title = card.title

            # Invalidate caches immediately so card appears in UI
            self._invalidate_caches()

            return {"id": card.id, "title": card.title, "status": card.status}
        finally:
            # Only close if we created the session (default factory).
            # Injected sessions (e.g., in tests) are managed by the caller.
            if self._uses_default_factory:
                session.close()

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

    async def run_track_a(self) -> AsyncGenerator[str, None]:
        """Track A: ensure embedding -> suggest links -> auto-create links."""
        if self.card_id is None:
            yield _sse("error", {"step": "track_a", "message": "No card_id — Phase 0 must run first"})
            return

        try:
            session = self._db_factory()
            try:
                svc = ZettelkastenService(session)
                from alfred.models.zettel import ZettelCard

                card = session.get(ZettelCard, self.card_id)
                if not card:
                    yield _sse("error", {"step": "track_a", "message": f"Card {self.card_id} not found"})
                    return

                # Step 1: Ensure embedding (generates + syncs to Qdrant)
                card = await asyncio.to_thread(svc.ensure_embedding, card)
                yield _sse("embedding_done", {"card_id": self.card_id})

                # Step 2: Find similar cards
                yield _sse("tool_start", {"step": "searching_kb"})
                suggestions = await asyncio.to_thread(
                    svc.suggest_links, self.card_id, min_confidence=0.6, limit=10
                )

                suggestion_data = [
                    {
                        "card_id": s.to_card_id,
                        "title": s.to_title,
                        "score": round(s.scores.composite_score, 2),
                        "reason": s.reason,
                    }
                    for s in suggestions
                ]
                yield _sse("links_found", {"suggestions": suggestion_data})

                # Step 3: Auto-create links above threshold
                auto_linked: list[dict[str, Any]] = []
                for s in suggestions:
                    if s.scores.composite_score >= AUTO_LINK_THRESHOLD:
                        links = await asyncio.to_thread(
                            svc.create_link,
                            from_card_id=self.card_id,
                            to_card_id=s.to_card_id,
                            type="auto_stream",
                            context=s.reason,
                            bidirectional=True,
                        )
                        for link in links:
                            auto_linked.append({
                                "id": link.id,
                                "source_id": link.from_card_id,
                                "target_id": link.to_card_id,
                                "type": link.type,
                            })
                if auto_linked:
                    yield _sse("links_created", {"links": auto_linked})

            finally:
                if self._uses_default_factory:
                    session.close()

        except Exception as exc:
            logger.warning("Track A failed for card %s: %s", self.card_id, exc, exc_info=True)
            yield _sse("error", {"step": "track_a", "message": str(exc)})

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
