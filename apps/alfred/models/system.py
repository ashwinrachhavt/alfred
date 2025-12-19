"""System-level relational models (SQLModel)."""

from __future__ import annotations

from sqlalchemy import Column, Index, String, Text
from sqlmodel import Field

from alfred.models.base import Model


class SystemSetting(Model, table=True):
    """Key/value store for small bits of configuration."""

    __tablename__ = "system_settings"
    __table_args__ = (Index("ix_system_settings_key", "key", unique=True),)

    key: str = Field(sa_column=Column(String(255), nullable=False))
    value: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
