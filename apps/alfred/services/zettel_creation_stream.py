"""Streaming zettel creation orchestrator.

Saves a card immediately, then runs two concurrent async tracks:
  Track A: embedding + Qdrant sync + vector search + auto-link
  Track B: o4-mini reasoning + enrichment + decomposition + gaps + Bloom inference

Yields SSE-formatted strings for each event.
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncGenerator, Callable
from typing import Any

from fastapi import Request
from sqlmodel import Session, select

from alfred.schemas.zettel import ZettelCardCreate
from alfred.services.sse_base import SSEStreamOrchestrator
from alfred.services.zettelkasten_service import ZettelkastenService

logger = logging.getLogger(__name__)


# Re-export the base class's static _sse at module level for backwards
# compatibility with callers that do:
#     from alfred.services.zettel_creation_stream import _sse
# (see tests/alfred/api/zettels/test_stream_routes.py and the existing
# service tests). Keeping this bound name stable lets T3's refactor stay
# invisible to external consumers.
_sse = SSEStreamOrchestrator._sse


AUTO_LINK_THRESHOLD = 0.75


class ZettelCreationStream(SSEStreamOrchestrator):
    """Streaming zettel creation: card save + embedding + links + Bloom + enrichment."""

    def __init__(
        self,
        payload: ZettelCardCreate,
        request: Request | None = None,
        db_session_factory: Callable[[], Session] | None = None,
    ) -> None:
        super().__init__(request=request, db_session_factory=db_session_factory)
        self.payload = payload
        self.card_id: int | None = None
        self._card_title: str = ""

    def _save_card_and_invalidate(self) -> dict[str, Any]:
        """Synchronous card save + cache invalidation. Runs in executor.

        Cache invalidation happens here (not Phase 2) so the card is visible
        in the UI immediately, even if the stream dies during enrichment.

        If the card is being written into a session, we also bump the
        session's ``updated_at`` so the T8 abandon-stale-sessions beat
        treats this as activity. Without this call the session's
        ``updated_at`` only reflects creation time and any newly-created
        session would be marked abandoned 24h later even if the user is
        actively writing into it.

        Sessions created from the default factory are properly closed via
        finally. Injected sessions (e.g., in tests) are managed by the caller.
        """
        session = self._db_factory()
        try:
            svc = ZettelkastenService(session)
            card = svc.create_card(**self.payload.model_dump())
            self.card_id = card.id
            self._card_title = card.title

            # Bump session.updated_at if this card belongs to a session so
            # the abandon-stale-sessions beat treats it as live activity.
            if self.payload.session_id is not None:
                try:
                    from alfred.services.session_service import SessionService

                    SessionService(session).touch(self.payload.session_id)
                except Exception:  # pragma: no cover - defensive
                    logger.warning(
                        "Failed to touch session %s after card save",
                        self.payload.session_id,
                        exc_info=True,
                    )

            # Invalidate caches immediately so card appears in UI
            self._invalidate_caches()

            # Best-effort Neo4j projection so the nexus view stays current.
            # Silent on failure — Postgres remains the source of truth.
            try:
                from alfred.core.dependencies import get_graph_service
                from alfred.services.zettel_graph_sync import ZettelGraphSync

                gs = get_graph_service()
                if gs is not None and card.id is not None:
                    ZettelGraphSync(session=session, graph=gs).upsert_card(card.id)
            except Exception:  # noqa: BLE001
                logger.debug("Neo4j upsert failed for streamed card %s", card.id, exc_info=True)

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
            yield self._sse("card_saved", result)
        except Exception as exc:
            logger.error("Phase 0 failed: %s", exc, exc_info=True)
            yield self._sse("error", {"step": "card_save", "message": str(exc)})

    async def run_track_a(self) -> AsyncGenerator[str, None]:
        """Track A: ensure embedding -> suggest links -> auto-create links."""
        if self.card_id is None:
            yield self._sse(
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
                    yield self._sse(
                        "error",
                        {"step": "track_a", "message": f"Card {self.card_id} not found"},
                    )
                    return

                # Step 1: Ensure embedding (generates + syncs to Qdrant)
                card = await asyncio.to_thread(svc.ensure_embedding, card)
                yield self._sse("embedding_done", {"card_id": self.card_id})

                # Step 2: Find similar cards
                yield self._sse("tool_start", {"step": "searching_kb"})
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
                yield self._sse("links_found", {"suggestions": suggestion_data})

                # Step 3: Auto-create links above threshold
                auto_linked: list[dict[str, Any]] = []
                created_link_ids: list[int] = []
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
                            if link.id is not None:
                                created_link_ids.append(link.id)
                if auto_linked:
                    yield self._sse("links_created", {"links": auto_linked})

                # Best-effort Neo4j projection of auto-created links.
                # Silent on failure — Postgres remains the source of truth.
                if created_link_ids:
                    try:
                        from alfred.core.dependencies import get_graph_service
                        from alfred.services.zettel_graph_sync import ZettelGraphSync

                        gs = get_graph_service()
                        if gs is not None:
                            sync = ZettelGraphSync(session=session, graph=gs)
                            for lid in created_link_ids:
                                sync.upsert_link(lid)
                    except Exception:  # noqa: BLE001
                        logger.debug(
                            "Neo4j link-upsert failed for streamed links %s",
                            created_link_ids,
                            exc_info=True,
                        )

            finally:
                if self._uses_default_factory:
                    session.close()

        except Exception as exc:
            logger.warning("Track A failed for card %s: %s", self.card_id, exc, exc_info=True)
            yield self._sse("error", {"step": "track_a", "message": str(exc)})

    async def run_track_b(self) -> AsyncGenerator[str, None]:
        """Track B: o4-mini reasoning + enrichment + decomposition + gaps + Bloom."""
        if self.card_id is None:
            yield self._sse(
                "error", {"step": "track_b", "message": "No card_id — Phase 0 must run first"}
            )
            return

        try:
            # Fetch lightweight KB context (prefer Redis cache)
            context = await asyncio.to_thread(self._fetch_kb_context)

            # Fetch sibling card titles if this card belongs to a session
            sibling_titles = await asyncio.to_thread(self._fetch_session_sibling_titles)

            # Build prompt (with session context if sibling_titles is non-empty)
            messages = self._build_analysis_prompt(context, sibling_titles)

            # Stream from reasoning model via the base-class helper (handles
            # reasoning-token pass-through and disconnect detection).
            from alfred.core.settings import settings

            model = settings.zettel_analysis_model

            completion_buffer = ""
            async for kind, content in self._run_openai_stream_with_reasoning(
                messages=messages,
                model=model,
                max_completion_tokens=4096,
            ):
                if kind == "thinking":
                    yield self._sse("thinking", {"content": content})
                elif kind == "completion":
                    completion_buffer += content

            # Parse the structured JSON response via the base-class parser.
            data = self._parse_structured_json(completion_buffer)
            if data is None:
                yield self._sse(
                    "error",
                    {"step": "track_b_parse", "message": "Failed to parse AI response"},
                )
                return

            # Existing order: enrichment, decomposition, gaps. Bloom LAST.
            if "enrichment" in data:
                yield self._sse("enrichment", data["enrichment"])
            if "decomposition" in data:
                yield self._sse("decomposition", data["decomposition"])
            if "gaps" in data:
                yield self._sse("gaps", data["gaps"])

            bloom = data.get("bloom_assessment")
            if bloom and isinstance(bloom, dict):
                level = bloom.get("inferred_level")
                rationale = bloom.get("rationale") or ""
                evidence_phrases = bloom.get("evidence_phrases") or []
                if isinstance(level, int) and 1 <= level <= 6:
                    # Emit the SSE event first so the client always gets the
                    # inference signal even if persistence fails.
                    yield self._sse(
                        "bloom_inferred",
                        {
                            "card_id": self.card_id,
                            "level": level,
                            "source": "ai_inferred",
                            "rationale": rationale,
                            "evidence_phrases": list(evidence_phrases),
                        },
                    )
                    try:
                        await asyncio.to_thread(
                            self._persist_bloom_inference,
                            level,
                            rationale,
                            list(evidence_phrases),
                        )
                    except Exception as exc:
                        logger.warning(
                            "Bloom persistence failed for card %s: %s",
                            self.card_id,
                            exc,
                            exc_info=True,
                        )
                        yield self._sse(
                            "error",
                            {"step": "bloom_persist", "message": str(exc)},
                        )

        except Exception as exc:
            logger.warning("Track B failed for card %s: %s", self.card_id, exc, exc_info=True)
            yield self._sse("error", {"step": "track_b", "message": str(exc)})

    def _persist_bloom_inference(
        self, level: int, rationale: str, evidence_phrases: list[str]
    ) -> None:
        """Persist Bloom fields without bumping updated_at.

        See the ``updated-at-corruption`` learning (cross-model, confidence 10/10):
        when saving *infrastructure* metadata about a card (Bloom inference,
        embedding coverage, etc.) the user-visible ``updated_at`` field must
        not be mutated. We use a Core UPDATE with ``synchronize_session=False``
        so the ORM does not attach column defaults; the only columns in the
        UPDATE set-clause are the Bloom ones. The model base declares
        ``updated_at`` as an *app-managed* default via ``default_factory`` — it
        is **not** mutated by SQLAlchemy event hooks — so omitting it from the
        UPDATE leaves its current value untouched.
        """
        if self.card_id is None:
            return
        from sqlalchemy import update as sa_update

        from alfred.core.utils import utcnow_naive
        from alfred.models.zettel import ZettelCard

        session = self._db_factory()
        try:
            # Read existing bloom_history inside the same transaction so we
            # can append the new entry deterministically.
            row = session.exec(
                select(ZettelCard.bloom_history).where(ZettelCard.id == self.card_id)
            ).one_or_none()
            # Normalise: sqlmodel .exec on a scalar select returns either the
            # scalar or a 1-tuple depending on driver shape.
            if isinstance(row, tuple):
                existing_history = row[0]
            else:
                existing_history = row
            new_entry = {
                "level": level,
                "source": "ai_inferred",
                "at": utcnow_naive().isoformat(),
                "rationale": rationale,
            }
            new_history = [*(existing_history or []), new_entry]

            stmt = (
                sa_update(ZettelCard)
                .where(ZettelCard.id == self.card_id)
                .values(
                    bloom_level=level,
                    bloom_source="ai_inferred",
                    bloom_history=new_history,
                )
                .execution_options(synchronize_session=False)
            )
            session.exec(stmt)
            session.commit()
        finally:
            if self._uses_default_factory:
                session.close()

    def _fetch_session_sibling_titles(self) -> list[str]:
        """Return titles of other cards in the same session (excludes this card's row)."""
        if self.payload.session_id is None:
            return []
        session = self._db_factory()
        try:
            from alfred.models.zettel import ZettelCard

            stmt = (
                select(ZettelCard.title)
                .where(ZettelCard.session_id == self.payload.session_id)
                .where(ZettelCard.id != (self.card_id or -1))
                .where(ZettelCard.status != "archived")
                .limit(20)
            )
            rows = session.exec(stmt).all()
            # sqlmodel's .exec on a single-column select may yield plain
            # strings OR 1-tuples depending on the engine/driver. Normalise.
            titles: list[str] = []
            for row in rows:
                if isinstance(row, tuple):
                    titles.append(row[0])
                else:
                    titles.append(row)
            return titles
        finally:
            if self._uses_default_factory:
                session.close()

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

    def _build_analysis_prompt(
        self,
        context: dict[str, Any],
        sibling_titles: list[str] | None = None,
    ) -> list[dict[str, str]]:
        """Build the o4-mini prompt for enrichment + decomposition + gaps + Bloom."""
        topics_str = (
            ", ".join(f"{t['topic']} ({t['count']})" for t in context.get("topics", []))
            or "none yet"
        )

        system = (
            "You are a knowledge analyst for a Zettelkasten system. "
            "The user is creating a new knowledge card. Analyze it and provide "
            "enrichment, decomposition assessment, knowledge gap analysis, and a "
            "Bloom's Taxonomy classification.\n\n"
            "Classify the card on Bloom's Taxonomy. "
            "Level 1 (Remember): bare facts or definitions. "
            "Level 2 (Understand): explanation in the user's own words. "
            "Level 3 (Apply): use in context. "
            "Level 4 (Analyze): decomposition or comparison. "
            "Level 5 (Evaluate): judgment or critique. "
            "Level 6 (Create): synthesis or new framing. "
            "Pick the LOWEST level that fits (err conservative).\n\n"
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
            "  },\n"
            '  "bloom_assessment": {\n'
            '    "inferred_level": 1-6,\n'
            '    "rationale": "one sentence",\n'
            '    "evidence_phrases": ["...", "..."]\n'
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
        if sibling_titles:
            user += (
                "\n\nThis card is being written alongside these sibling cards "
                f"in the same session: {', '.join(sibling_titles)}. "
                "Consider cross-linking in your analysis."
            )

        return [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]

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
            yield self._sse("done", {"card": None, "stats": {"error": "card_save_failed"}})
            return

        # Phase 1: run Track A and Track B concurrently, merge their events
        async for event in merge_async_generators(self.run_track_a(), self.run_track_b()):
            yield event

        # Phase 2: fetch final card state
        final_card = await asyncio.to_thread(self._fetch_final_card)
        yield self._sse("done", {"card": final_card, "stats": {"card_id": self.card_id}})
