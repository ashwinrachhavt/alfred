"""User model for authentication/admin management."""

from __future__ import annotations

import sqlalchemy as sa
from sqlmodel import Field

from alfred.models.base import Model


class User(Model, table=True):
    """Application user account."""

    __tablename__ = "users"
    __table_args__ = (
        sa.Index("ix_users_email", "email", unique=True),
        sa.Index("ix_users_created_at", "created_at"),
    )

    email: str = Field(sa_column=sa.Column(sa.String(length=255), nullable=False, unique=True))
    full_name: str | None = Field(default=None, sa_column=sa.Column(sa.String(length=255)))
    hashed_password: str | None = Field(
        default=None, sa_column=sa.Column(sa.String(length=255), nullable=True)
    )
    is_active: bool = Field(default=True, sa_column=sa.Column(sa.Boolean, nullable=False))
    is_superuser: bool = Field(default=False, sa_column=sa.Column(sa.Boolean, nullable=False))


__all__ = ["User"]
