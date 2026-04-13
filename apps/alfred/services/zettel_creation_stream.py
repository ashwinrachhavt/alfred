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
            yield _sse(
                "error", {"step": "track_a", "message": "No card_id — Phase 0 must run first"}
            )
            return

        try:
            session = self._db_factory()
            try:
                svc = ZettelkastenService(session)
                from alfred.models.zettel import ZettelCard

                card = session.get(ZettelCard, self.card_id)
                if not card:
                    yield _sse(
                        "error", {"step": "track_a", "message": f"Card {self.card_id} not found"}
                    )
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
                            auto_linked.append(
                                {
                                    "id": link.id,
                                    "source_id": link.from_card_id,
                                    "target_id": link.to_card_id,
                                    "type": link.type,
                                }
                            )
                if auto_linked:
                    yield _sse("links_created", {"links": auto_linked})

            finally:
                if self._uses_default_factory:
                    session.close()

        except Exception as exc:
            logger.warning("Track A failed for card %s: %s", self.card_id, exc, exc_info=True)
            yield _sse("error", {"step": "track_a", "message": str(exc)})

    async def run_track_b(self) -> AsyncGenerator[str, None]:
        """Track B: o4-mini reasoning + enrichment + decomposition + gaps."""
        if self.card_id is None:
            yield _sse(
                "error", {"step": "track_b", "message": "No card_id — Phase 0 must run first"}
            )
            return

        try:
            # Fetch lightweight KB context (prefer Redis cache)
            context = await asyncio.to_thread(self._fetch_kb_context)

            # Build prompt
            messages = self._build_analysis_prompt(context)

            # Stream from reasoning model
            from alfred.core.llm_factory import get_async_openai_client
            from alfred.core.settings import settings

            client = get_async_openai_client()
            model = settings.zettel_analysis_model

            completion_buffer = ""
            stream = await client.chat.completions.create(
                model=model,
                messages=messages,
                stream=True,
                max_completion_tokens=4096,
            )

            async for chunk in stream:
                if not chunk.choices:
                    continue
                delta = chunk.choices[0].delta

                # Reasoning tokens (o3/o4 models)
                reasoning = getattr(delta, "reasoning", None) or getattr(
                    delta, "reasoning_content", None
                )
                if reasoning:
                    yield _sse("thinking", {"content": reasoning})

                # Completion tokens (the JSON response)
                if delta.content:
                    completion_buffer += delta.content

            # Parse the structured JSON response
            if completion_buffer:
                for event in self._parse_analysis_response(completion_buffer):
                    yield event

        except Exception as exc:
            logger.warning("Track B failed for card %s: %s", self.card_id, exc, exc_info=True)
            yield _sse("error", {"step": "track_b", "message": str(exc)})

    def _fetch_kb_context(self) -> dict[str, Any]:
        """Fetch lightweight KB context for the AI prompt. Prefers Redis cache."""
        # Try Redis cache first
        try:
            from alfred.core.redis_client import get_redis_client

            redis = get_redis_client()
            if redis:
                cached_topics = redis.get("zettel:topics:distribution")
                if cached_topics:
                    return json.loads(cached_topics)
        except Exception:
            pass

        # Fall back to DB
        session = self._db_factory()
        try:
            from sqlalchemy import func as sa_func
            from sqlmodel import select

            from alfred.models.zettel import ZettelCard

            total = session.exec(
                select(sa_func.count())
                .select_from(ZettelCard)
                .where(ZettelCard.status != "archived")
            ).one()

            topics_rows = session.exec(
                select(ZettelCard.topic, sa_func.count())
                .where(ZettelCard.topic.isnot(None), ZettelCard.status != "archived")
                .group_by(ZettelCard.topic)
                .order_by(sa_func.count().desc())
                .limit(30)
            ).all()

            return {
                "total_cards": total,
                "topics": [{"topic": t, "count": c} for t, c in topics_rows],
            }
        finally:
            if self._uses_default_factory:
                session.close()

    def _build_analysis_prompt(self, context: dict[str, Any]) -> list[dict[str, str]]:
        """Build the o4-mini prompt for enrichment + decomposition + gaps."""
        topics_str = (
            ", ".join(f"{t['topic']} ({t['count']})" for t in context.get("topics", []))
            or "none yet"
        )

        system = (
            "You are a knowledge analyst for a Zettelkasten system. "
            "The user is creating a new knowledge card. Analyze it and provide "
            "enrichment, decomposition assessment, and knowledge gap analysis.\n\n"
            f"Knowledge base context:\n"
            f"- Total cards: {context.get('total_cards', 0)}\n"
            f"- Topics (with card counts): {topics_str}\n\n"
            "Respond ONLY with valid JSON (no markdown fences, no commentary):\n"
            "{\n"
            '  "enrichment": {\n'
            '    "suggested_title": "..." or null (only if meaningfully better),\n'
            '    "summary": "one-sentence distillation",\n'
            '    "suggested_tags": ["tag1", "tag2"],\n'
            '    "suggested_topic": "..." or null\n'
            "  },\n"
            '  "decomposition": {\n'
            '    "is_atomic": true/false,\n'
            '    "reason": "why or why not",\n'
            '    "suggested_cards": [{"title": "...", "content": "..."}]\n'
            "  },\n"
            '  "gaps": {\n'
            '    "missing_topics": ["topic1"],\n'
            '    "weak_areas": [{"topic": "...", "existing_count": N, "note": "..."}]\n'
            "  }\n"
            "}"
        )

        content_str = self.payload.content or ""
        tags_str = ", ".join(self.payload.tags or [])
        user = (
            f"New card being created:\n"
            f"Title: {self.payload.title}\n"
            f"Content: {content_str}\n"
            f"Tags: {tags_str}\n"
            f"Topic: {self.payload.topic or 'not set'}"
        )

        return [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]

    def _parse_analysis_response(self, raw: str) -> list[str]:
        """Parse the JSON response from the analysis model into SSE events."""
        events: list[str] = []
        try:
            cleaned = raw.strip()
            if cleaned.startswith("```"):
                cleaned = "\n".join(cleaned.split("\n")[1:])
            if cleaned.endswith("```"):
                cleaned = "\n".join(cleaned.split("\n")[:-1])
            cleaned = cleaned.strip()

            data = json.loads(cleaned)

            if "enrichment" in data:
                events.append(_sse("enrichment", data["enrichment"]))
            if "decomposition" in data:
                events.append(_sse("decomposition", data["decomposition"]))
            if "gaps" in data:
                events.append(_sse("gaps", data["gaps"]))

        except (json.JSONDecodeError, KeyError) as exc:
            logger.warning("Failed to parse Track B response: %s", exc)
            events.append(
                _sse(
                    "error",
                    {"step": "track_b_parse", "message": f"Failed to parse AI response: {exc}"},
                )
            )

        return events

    def _fetch_final_card(self) -> dict[str, Any]:
        """Fetch the final card state for the done event."""
        session = self._db_factory()
        try:
            from alfred.models.zettel import ZettelCard

            card = session.get(ZettelCard, self.card_id)
            if not card:
                return {"id": self.card_id}
            return {
                "id": card.id,
                "title": card.title,
                "content": card.content,
                "summary": card.summary,
                "tags": card.tags,
                "topic": card.topic,
                "status": card.status,
                "importance": card.importance,
                "confidence": card.confidence,
                "created_at": card.created_at.isoformat() if card.created_at else None,
                "updated_at": card.updated_at.isoformat() if card.updated_at else None,
            }
        finally:
            if self._uses_default_factory:
                session.close()

    async def run(self) -> AsyncGenerator[str, None]:
        """Full pipeline: Phase 0 -> Phase 1 (concurrent tracks) -> Phase 2."""
        from alfred.core.async_merge import merge_async_generators

        # Phase 0: save card + invalidate caches
        async for event in self.run_phase0():
            yield event

        if self.card_id is None:
            # Phase 0 failed — emit done and stop
            yield _sse("done", {"card": None, "stats": {"error": "card_save_failed"}})
            return

        # Phase 1: run Track A and Track B concurrently, merge their events
        async for event in merge_async_generators(self.run_track_a(), self.run_track_b()):
            yield event

        # Phase 2: fetch final card state
        final_card = await asyncio.to_thread(self._fetch_final_card)
        yield _sse("done", {"card": final_card, "stats": {"card_id": self.card_id}})
