"""Research-related ORM models (SQLModel)."""

from __future__ import annotations

from sqlalchemy import JSON, Column, Integer, String, Text
from sqlmodel import Field

from alfred.models.base import Model


class ResearchRun(Model, table=True):
    """Persists generated research drafts and their metadata."""

    __tablename__ = "research_runs"

    query: str = Field(sa_column=Column(Text, nullable=False))
    target_length_words: int = Field(sa_column=Column(Integer, nullable=False))
    tone: str = Field(sa_column=Column(String(32), nullable=False))
    article: str = Field(sa_column=Column(Text, nullable=False))
    state: dict | list | None = Field(sa_column=Column(JSON, nullable=False))
