"""Vocabulary / dictionary domain model."""

from __future__ import annotations

import enum

from sqlalchemy import JSON, Column, ForeignKey, Index, Integer, SmallInteger, String, Text
from sqlmodel import Field

from alfred.models.base import Model


class SaveIntent(str, enum.Enum):
    """Why the user saved this word."""

    learning = "learning"
    reference = "reference"
    encountered = "encountered"


class VocabularyEntry(Model, table=True):
    """A personal dictionary entry combining external definitions with user annotations."""

    __tablename__ = "vocabulary_entries"
    __table_args__ = (
        Index("ix_vocabulary_entries_word", "word"),
        Index("ix_vocabulary_entries_user_id", "user_id"),
        Index("ix_vocabulary_entries_save_intent", "save_intent"),
    )

    user_id: int | None = Field(default=None, sa_column=Column(Integer, nullable=True))
    word: str = Field(sa_column=Column(String(255), nullable=False))
    language: str = Field(default="en", sa_column=Column(String(10), nullable=False))

    # Pronunciation
    pronunciation_ipa: str | None = Field(default=None, sa_column=Column(String(512), nullable=True))
    pronunciation_audio_url: str | None = Field(
        default=None, sa_column=Column(String(2048), nullable=True)
    )

    # Structured data from external sources
    definitions: list | None = Field(default=None, sa_column=Column(JSON, nullable=True))
    etymology: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    synonyms: list | None = Field(default=None, sa_column=Column(JSON, nullable=True))
    antonyms: list | None = Field(default=None, sa_column=Column(JSON, nullable=True))
    usage_notes: str | None = Field(default=None, sa_column=Column(Text, nullable=True))

    # External content
    wikipedia_summary: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    ai_explanation: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    ai_explanation_domains: list | None = Field(default=None, sa_column=Column(JSON, nullable=True))
    source_urls: list | None = Field(default=None, sa_column=Column(JSON, nullable=True))

    # Personal
    personal_notes: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    domain_tags: list | None = Field(default=None, sa_column=Column(JSON, nullable=True))
    save_intent: str = Field(
        default=SaveIntent.learning.value, sa_column=Column(String(32), nullable=False)
    )
    bloom_level: int = Field(default=1, sa_column=Column(SmallInteger, nullable=False))

    # Phase 2: knowledge graph link
    zettel_id: int | None = Field(
        default=None,
        sa_column=Column(Integer, ForeignKey("zettel_cards.id"), nullable=True),
    )
