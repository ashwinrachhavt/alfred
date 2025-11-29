"""Research-related ORM models."""

from __future__ import annotations

from sqlalchemy import JSON, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from alfred.models.base import Model


class ResearchRun(Model):
    """Persists generated research drafts and their metadata."""

    __tablename__ = "research_runs"

    query: Mapped[str] = mapped_column(Text, nullable=False)
    target_length_words: Mapped[int] = mapped_column(Integer, nullable=False)
    tone: Mapped[str] = mapped_column(String(32), nullable=False)
    article: Mapped[str] = mapped_column(Text, nullable=False)
    state: Mapped[dict | list | None] = mapped_column(JSON, nullable=False)
