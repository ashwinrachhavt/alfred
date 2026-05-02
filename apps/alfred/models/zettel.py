"""Zettelkasten domain models (SQLModel-backed).

These tables capture atomic knowledge cards, their links, and spaced
repetition reviews. They are intentionally lightweight so the API can layer
graph views and progress calculations on top.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy import text as sa_text
from sqlmodel import Field

from alfred.models.base import Model


class ZettelCard(Model, table=True):
    """A single knowledge card.

    Cards are intentionally small: a title, optional content/summary, tags, and
    references back to source material (document_id/source_url). The
    ``importance`` and ``confidence`` fields allow lightweight readiness
    tracking without forcing a full rubric.

    Bloom/session augmentation (T1):
        * ``session_id`` links the card to a ZettelSession (a sitting in
          which the user creates multiple related cards).
        * ``bloom_level`` (1..6) tracks Bloom's Taxonomy depth for the
          card. Always set — existing rows are backfilled to ``1``.
        * ``bloom_source`` records *how* the level was arrived at
          (``backfill``/``ai_inferred``/``user_set``/``review_updated``).
        * ``bloom_history`` keeps an audit trail of level transitions.
        * ``enrichment_attempted_at``/``enrichment_last_error`` let the
          workspace derive enrichment state without a dedicated enum.
    """

    __tablename__ = "zettel_cards"
    __table_args__ = (
        Index("ix_zettel_cards_topic", "topic"),
        Index("ix_zettel_cards_title", "title"),
        Index("ix_zettel_cards_status", "status"),
        Index("ix_zettel_cards_document_id", "document_id"),
        Index("ix_zettel_cards_updated_at", "updated_at"),
        Index(
            "ix_zettel_cards_session_id",
            "session_id",
            postgresql_where=sa_text("session_id IS NOT NULL"),
        ),
    )

    title: str = Field(sa_column=Column(String(255), nullable=False))
    content: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    summary: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    tags: list[str] | None = Field(default=None, sa_column=Column(JSON, nullable=True))
    topic: str | None = Field(default=None, sa_column=Column(String(128), nullable=True))
    source_url: str | None = Field(default=None, sa_column=Column(String(2048), nullable=True))
    document_id: str | None = Field(default=None, sa_column=Column(String(96), nullable=True))
    status: str = Field(default="active", sa_column=Column(String(32), nullable=False))
    importance: int = Field(default=0, sa_column=Column(Integer, nullable=False))
    confidence: float = Field(default=0.0, sa_column=Column(Float, nullable=False))
    embedding: list[float] | None = Field(default=None, sa_column=Column(JSON, nullable=True))

    # --- T1: session + Bloom + enrichment columns ---------------------------------
    session_id: int | None = Field(
        default=None,
        sa_column=Column(Integer, ForeignKey("zettel_sessions.id"), nullable=True),
    )
    bloom_level: int = Field(default=1, sa_column=Column(Integer, nullable=False))
    bloom_source: str = Field(default="backfill", sa_column=Column(String(32), nullable=False))
    bloom_history: list[dict] | None = Field(default=None, sa_column=Column(JSON, nullable=True))
    enrichment_attempted_at: datetime | None = Field(
        default=None, sa_column=Column(DateTime, nullable=True)
    )
    enrichment_last_error: str | None = Field(default=None, sa_column=Column(Text, nullable=True))


class ZettelSession(Model, table=True):
    """A sitting in which the user creates multiple zettels with shared context.

    Status is derived, not stored (D4), to prevent desync between redundant fields:
        * ``active``    — ``ended_at IS NULL``
        * ``ended``     — ``ended_at IS NOT NULL`` AND ``summary_card_id IS NOT NULL``
        * ``abandoned`` — ``ended_at IS NOT NULL`` AND ``summary_card_id IS NULL``
    """

    __tablename__ = "zettel_sessions"
    __table_args__ = (
        Index(
            "ix_zettel_sessions_active",
            "ended_at",
            postgresql_where=sa_text("ended_at IS NULL"),
        ),
    )

    title: str | None = Field(default=None, sa_column=Column(String(255), nullable=True))
    shared_topic: str | None = Field(default=None, sa_column=Column(String(128), nullable=True))
    shared_tags: list[str] | None = Field(default=None, sa_column=Column(JSON, nullable=True))
    source_context: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    ended_at: datetime | None = Field(default=None, sa_column=Column(DateTime, nullable=True))
    summary: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    card_count: int = Field(default=0, sa_column=Column(Integer, nullable=False))
    summary_card_id: int | None = Field(
        default=None,
        sa_column=Column(Integer, ForeignKey("zettel_cards.id"), nullable=True),
    )

    @property
    def status(self) -> str:
        """Derived: ``active`` | ``ended`` | ``abandoned``. See D4 in the plan."""

        if self.ended_at is None:
            return "active"
        return "ended" if self.summary_card_id is not None else "abandoned"


class ZettelLink(Model, table=True):
    """Directed relationship between two cards."""

    __tablename__ = "zettel_links"
    __table_args__ = (
        Index("ix_zettel_links_from", "from_card_id"),
        Index("ix_zettel_links_to", "to_card_id"),
        Index("ix_zettel_links_unique", "from_card_id", "to_card_id", "type", unique=True),
    )

    from_card_id: int = Field(
        sa_column=Column(Integer, ForeignKey("zettel_cards.id"), nullable=False)
    )
    to_card_id: int = Field(
        sa_column=Column(Integer, ForeignKey("zettel_cards.id"), nullable=False)
    )
    type: str = Field(default="reference", sa_column=Column(String(64), nullable=False))
    context: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    bidirectional: bool = Field(default=True, sa_column=Column(Boolean, nullable=False))


class WikiLink(Model, table=True):
    """Wiki-link from a note or zettel card to a target zettel card.

    Uses polymorphic source identification (source_type + source_id as text)
    to avoid mixing int/UUID FK types in one table. The target is always a
    ZettelCard (int FK).
    """

    __tablename__ = "wiki_links"
    __table_args__ = (
        Index("ix_wiki_links_source", "source_type", "source_id"),
        Index("ix_wiki_links_target", "target_card_id"),
        Index(
            "ix_wiki_links_unique",
            "source_type",
            "source_id",
            "target_card_id",
            unique=True,
        ),
    )

    source_type: str = Field(sa_column=Column(String(16), nullable=False))  # "note" | "zettel"
    source_id: str = Field(sa_column=Column(String(64), nullable=False))  # UUID or int as string
    target_card_id: int = Field(
        sa_column=Column(Integer, ForeignKey("zettel_cards.id"), nullable=False)
    )


class ZettelReview(Model, table=True):
    """Spaced repetition review scheduled for a card."""

    __tablename__ = "zettel_reviews"
    __table_args__ = (
        Index("ix_zettel_reviews_card_id", "card_id"),
        Index("ix_zettel_reviews_due_at", "due_at"),
        Index("ix_zettel_reviews_open_due", "completed_at", "due_at"),
    )

    card_id: int = Field(sa_column=Column(Integer, ForeignKey("zettel_cards.id"), nullable=False))
    stage: int = Field(sa_column=Column(Integer, nullable=False))
    iteration: int = Field(default=1, sa_column=Column(Integer, nullable=False))
    due_at: datetime = Field(sa_column=Column(DateTime, nullable=False))
    completed_at: datetime | None = Field(default=None, sa_column=Column(DateTime, nullable=True))
    score: float | None = Field(default=None, sa_column=Column(Float, nullable=True))
