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
from sqlmodel import Field

from alfred.models.base import Model


class ZettelCard(Model, table=True):
    """A single knowledge card.

    Cards are intentionally small: a title, optional content/summary, tags, and
    references back to source material (document_id/source_url). The
    ``importance`` and ``confidence`` fields allow lightweight readiness
    tracking without forcing a full rubric.
    """

    __tablename__ = "zettel_cards"
    __table_args__ = (
        Index("ix_zettel_cards_topic", "topic"),
        Index("ix_zettel_cards_title", "title"),
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
