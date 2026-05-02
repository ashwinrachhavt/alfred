"""ZettelSession service (T6).

Handles session CRUD, the End-session Bloom-6 summary generation, and the
D13 hydrate projection (top-3 full cards + stubs).

The session lifecycle (D4) is:
    * active    -- ended_at IS NULL
    * ended     -- ended_at IS NOT NULL AND summary_card_id IS NOT NULL
    * abandoned -- ended_at IS NOT NULL AND summary_card_id IS NULL
        (empty sessions ended by the user, no cards to summarize)

Status is derived, never stored; see ZettelSession.status property.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from sqlmodel import Session, select

from alfred.core.llm_factory import get_chat_model
from alfred.core.settings import settings
from alfred.core.utils import utcnow_naive as _utcnow
from alfred.models.zettel import ZettelCard, ZettelSession
from alfred.schemas.zettel import (
    ZettelCardOut,
    ZettelCardStub,
    ZettelSessionCreateRequest,
    ZettelSessionHydrateResponse,
    ZettelSessionOut,
)
from alfred.services.zettelkasten_service import ZettelkastenService

log = logging.getLogger(__name__)

# How many cards render with full state on session rehydration (D13).
HYDRATE_FULL_LIMIT = 3


class SessionNotFound(Exception):
    """Raised when a session id does not exist."""


class SessionAlreadyEnded(Exception):
    """Raised when end() is called twice on the same session."""

    def __init__(self, session: ZettelSession) -> None:
        super().__init__(f"Session {session.id} already ended at {session.ended_at}")
        self.session = session


@dataclass
class SessionService:
    """Domain service for ZettelSession lifecycle."""

    session: Session

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def create(self, payload: ZettelSessionCreateRequest) -> ZettelSession:
        row = ZettelSession(
            title=payload.title.strip() if payload.title else None,
            shared_topic=payload.shared_topic.strip() if payload.shared_topic else None,
            shared_tags=payload.shared_tags or None,
            source_context=payload.source_context,
        )
        self.session.add(row)
        self.session.commit()
        self.session.refresh(row)
        return row

    def get(self, session_id: int) -> ZettelSession | None:
        return self.session.get(ZettelSession, session_id)

    def touch(self, session_id: int) -> None:
        """Bump ``updated_at`` on the session row (activity signal).

        T8 relies on ``updated_at`` as the staleness signal for the
        abandon-stale-sessions Celery beat. Creating a card with
        ``session_id=X`` moves the *card's* updated_at but not the
        session's, so we need an explicit "a thing happened here" poke
        whenever the user acts inside a session.

        Unlike the Bloom inference write, ``updated_at`` IS the column
        we intend to change here — this is the opposite of the
        ``updated-at-corruption`` pattern. We use a Core UPDATE with
        ``synchronize_session=False`` to avoid ORM identity-map side
        effects, and explicitly set ``updated_at`` in the SET clause.
        No-op (does not raise) when ``session_id`` does not exist; the
        orchestrator path should not fail closed on a stale touch.
        """
        from sqlalchemy import update as sa_update

        stmt = (
            sa_update(ZettelSession)
            .where(ZettelSession.id == session_id)
            .values(updated_at=_utcnow())
            .execution_options(synchronize_session=False)
        )
        self.session.exec(stmt)
        self.session.commit()

    def end(self, session_id: int) -> ZettelSession:
        """End the session.

        Empty sessions (0 active, non-summary cards) become abandoned
        with no summary card. This is the "ended an empty session by
        accident" path.

        Sessions with >= 1 card produce a Bloom-6 synthesis card via the
        LLM, auto-linked to every source card. If the LLM fails or
        returns empty output, fall back to a deterministic summary so
        the session always has something.
        """
        sess = self.get(session_id)
        if not sess:
            raise SessionNotFound(str(session_id))
        if sess.ended_at is not None:
            raise SessionAlreadyEnded(sess)

        active_cards = self._active_session_cards(sess)

        if not active_cards:
            # Empty-session no-op branch: mark ended, no summary card.
            sess.ended_at = _utcnow()
            self.session.add(sess)
            self.session.commit()
            self.session.refresh(sess)
            return sess

        # card_count >= 1: synthesize a Bloom-6 summary card.
        summary_text = self._generate_summary_text(sess, active_cards)

        svc = ZettelkastenService(self.session)
        summary_card = svc.create_card(
            title=self._summary_card_title(sess),
            content=summary_text,
            summary=summary_text,
            tags=["session-summary"],
            topic=sess.shared_topic,
            session_id=sess.id,
            bloom_level=6,
            bloom_source="ai_inferred",
        )

        # Auto-link the summary card to every other card in the session.
        for card in active_cards:
            if card.id is None or card.id == summary_card.id:
                continue
            try:
                svc.create_link(
                    from_card_id=summary_card.id or 0,
                    to_card_id=card.id,
                    type="session_summary",
                    bidirectional=True,
                )
            except Exception:  # pragma: no cover - defensive; link is best-effort
                log.warning(
                    "session_summary link failed: %s -> %s",
                    summary_card.id,
                    card.id,
                    exc_info=True,
                )

        sess.summary = summary_text
        sess.summary_card_id = summary_card.id
        sess.ended_at = _utcnow()
        self.session.add(sess)
        self.session.commit()
        self.session.refresh(sess)
        return sess

    def hydrate(self, session_id: int) -> ZettelSessionHydrateResponse:
        sess = self.get(session_id)
        if not sess:
            raise SessionNotFound(str(session_id))

        # Top-N active cards (most recently updated) hydrated in full.
        full_stmt = (
            select(ZettelCard)
            .where(ZettelCard.session_id == sess.id)
            .where(ZettelCard.status != "archived")
            .order_by(ZettelCard.updated_at.desc())
            .limit(HYDRATE_FULL_LIMIT)
        )
        full_cards = list(self.session.exec(full_stmt))
        full_ids = {c.id for c in full_cards if c.id is not None}

        # Everything else; include archived, marked via is_archived.
        stub_stmt = (
            select(ZettelCard)
            .where(ZettelCard.session_id == sess.id)
            .order_by(ZettelCard.updated_at.desc())
        )
        stub_rows = [
            c for c in self.session.exec(stub_stmt) if c.id is not None and c.id not in full_ids
        ]

        return ZettelSessionHydrateResponse(
            session=to_session_out(sess),
            full_cards=[ZettelCardOut.model_validate(c) for c in full_cards],
            stub_cards=[
                ZettelCardStub(
                    id=c.id or 0,
                    title=c.title,
                    bloom_level=c.bloom_level,
                    created_at=c.created_at,
                    updated_at=c.updated_at,
                    is_archived=c.status == "archived",
                )
                for c in stub_rows
            ],
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _active_session_cards(self, sess: ZettelSession) -> list[ZettelCard]:
        """User-authored active cards in the session.

        Excludes archived rows AND the existing summary card (if any) so
        card_count reflects what the user actually wrote during the
        sitting.
        """
        stmt = (
            select(ZettelCard)
            .where(ZettelCard.session_id == sess.id)
            .where(ZettelCard.status != "archived")
            .order_by(ZettelCard.created_at.asc())
        )
        rows = list(self.session.exec(stmt))
        if sess.summary_card_id is not None:
            rows = [c for c in rows if c.id != sess.summary_card_id]
        # Defensive: also drop anything tagged session-summary (handles
        # sessions where the summary row exists but the FK was not yet
        # populated).
        rows = [c for c in rows if "session-summary" not in (c.tags or [])]
        return rows

    def _summary_card_title(self, sess: ZettelSession) -> str:
        topic = sess.shared_topic or sess.title or "knowledge"
        return f"Session synthesis: {topic}"

    def _deterministic_summary(self, sess: ZettelSession, cards: list[ZettelCard]) -> str:
        topic = sess.shared_topic or "knowledge"
        first_titles = [c.title for c in cards[:3] if c.title]
        titles_blurb = ", ".join(first_titles) if first_titles else "assorted ideas"
        return f"Sitting on {topic}: {len(cards)} cards covering {titles_blurb}."

    def _generate_summary_text(self, sess: ZettelSession, cards: list[ZettelCard]) -> str:
        """Generate the Bloom-6 synthesis paragraph.

        On any failure or empty/whitespace response, fall back to a
        deterministic summary so the session always has body text.
        """
        try:
            text = self._call_llm_for_summary(sess, cards)
        except Exception as exc:  # LLM/network/timeout are all fallback-worthy
            log.warning("session summary LLM call failed: %s", exc, exc_info=True)
            return self._deterministic_summary(sess, cards)

        if not text or not text.strip():
            return self._deterministic_summary(sess, cards)
        return text.strip()

    def _call_llm_for_summary(self, sess: ZettelSession, cards: list[ZettelCard]) -> str:
        topic = sess.shared_topic or "various topics"
        lines: list[str] = []
        for idx, card in enumerate(cards, start=1):
            title = (card.title or "").strip() or f"Card {idx}"
            summary = (card.summary or card.content or "").strip()
            if summary:
                lines.append(f"{idx}. {title} - {summary}")
            else:
                lines.append(f"{idx}. {title}")
        body = "\n".join(lines)

        system_msg = (
            "You are summarizing a Zettelkasten sitting. "
            "Produce a Bloom Level 6 (Create) synthesis: one paragraph "
            "(3-5 sentences) that states what the cards collectively "
            "argue or discover. Do not repeat the cards; synthesize. "
            "Respond ONLY with the paragraph text, no JSON, no markdown."
        )
        user_msg = (
            f"The user wrote {len(cards)} cards on the topic '{topic}'. "
            f"Titles and summaries follow.\n\n{body}"
        )

        llm = get_chat_model(model=settings.zettel_analysis_model)
        response = llm.invoke(
            [
                {"role": "system", "content": system_msg},
                {"role": "user", "content": user_msg},
            ]
        )
        raw = response.content if hasattr(response, "content") else str(response)
        if isinstance(raw, list):  # some providers return content parts
            raw = "".join(
                part.get("text", "") if isinstance(part, dict) else str(part) for part in raw
            )
        return str(raw or "")


def to_session_out(sess: ZettelSession) -> ZettelSessionOut:
    """Construct a ZettelSessionOut, populating the derived status field."""
    return ZettelSessionOut(
        id=sess.id or 0,
        title=sess.title,
        shared_topic=sess.shared_topic,
        shared_tags=sess.shared_tags,
        source_context=sess.source_context,
        ended_at=sess.ended_at,
        summary=sess.summary,
        card_count=sess.card_count,
        summary_card_id=sess.summary_card_id,
        status=sess.status,
        created_at=sess.created_at,
        updated_at=sess.updated_at,
    )


__all__ = [
    "SessionAlreadyEnded",
    "SessionNotFound",
    "SessionService",
    "to_session_out",
]
