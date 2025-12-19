"""SQLModel base classes and mixins for ORM models."""

from __future__ import annotations

from datetime import datetime

from sqlmodel import Field, SQLModel


class TimestampMixin(SQLModel):
    """Adds created/updated timestamps (app-managed)."""

    created_at: datetime | None = Field(default_factory=lambda: datetime.utcnow())
    updated_at: datetime | None = Field(default_factory=lambda: datetime.utcnow())


class Model(TimestampMixin, SQLModel):
    """Opinionated base with `id`/timestamps for SQLModel tables.

    Inherit this along with `table=True` on concrete models.
    """

    id: int | None = Field(default=None, primary_key=True)
