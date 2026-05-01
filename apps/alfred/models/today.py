"""Today/Daily domain models: entries and reflections."""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import JSON, Column, Date, DateTime, Index, Integer, String, Text
from sqlmodel import Field

from alfred.models.base import Model


class DailyEntryRow(Model, table=True):
    """A single item captured for a given day (todo | note | learning).

    ``artifact_ref`` kind is NOT a stored value — it is synthesized at read
    time when joining user-created cards/zettels/documents onto the day.
    """

    __tablename__ = "daily_entries"
    __table_args__ = (
        Index("ix_daily_entries_date", "entry_date"),
        Index("ix_daily_entries_date_kind", "entry_date", "kind"),
        Index("ix_daily_entries_user_date", "user_id", "entry_date"),
    )

    user_id: str | None = Field(default=None, sa_column=Column(String(255), nullable=True))
    entry_date: date = Field(sa_column=Column(Date, nullable=False))
    kind: str = Field(sa_column=Column(String(32), nullable=False))  # todo | note | learning
    title: str = Field(sa_column=Column(String(500), nullable=False))
    body_md: str = Field(default="", sa_column=Column(Text, nullable=False))
    status: str = Field(default="open", sa_column=Column(String(16), nullable=False))
    priority: int = Field(default=0, sa_column=Column(Integer, nullable=False))
    tags: list[str] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    meta: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))


class DailyReflectionRow(Model, table=True):
    """End-of-day digest produced by the reflection pipeline.

    One reflection per day per user (single-user deployment). The UNIQUE
    index on ``entry_date`` enforces that invariant at the DB level.
    """

    __tablename__ = "daily_reflections"
    __table_args__ = (Index("ix_daily_reflections_date", "entry_date", unique=True),)

    user_id: str | None = Field(default=None, sa_column=Column(String(255), nullable=True))
    entry_date: date = Field(sa_column=Column(Date, nullable=False))
    digest_md: str = Field(default="", sa_column=Column(Text, nullable=False))
    stats: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    pipeline_run_id: str = Field(sa_column=Column(String(64), nullable=False))
    stages_ran: list[str] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    generated_at: datetime = Field(sa_column=Column(DateTime(timezone=True), nullable=False))


__all__ = ["DailyEntryRow", "DailyReflectionRow"]
