"""System-level relational models."""

from __future__ import annotations

from sqlalchemy import Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from alfred.models.base import Model


class SystemSetting(Model):
    """Key/value store for small bits of configuration."""

    __tablename__ = "system_settings"
    __table_args__ = (Index("ix_system_settings_key", "key", unique=True),)

    key: Mapped[str] = mapped_column(String(255), nullable=False)
    value: Mapped[str | None] = mapped_column(Text, nullable=True)
