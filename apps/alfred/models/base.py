"""SQLModel base classes and mixins for ORM models."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlmodel import Field, SQLModel


class TimestampMixin(SQLModel):
    """Adds created/updated timestamps (app-managed)."""

    created_at: datetime | None = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime | None = Field(default_factory=lambda: datetime.now(UTC))


class Model(TimestampMixin, SQLModel):
    """Opinionated base with `id`/timestamps for SQLModel tables.

    Inherit this along with `table=True` on concrete models.
    """

    id: int | None = Field(default=None, primary_key=True)
