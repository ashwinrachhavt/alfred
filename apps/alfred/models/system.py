"""System-level models."""

from __future__ import annotations

from alfred.models import Mapped, Model, fields


class SystemSetting(Model):
    """Key-value store for feature flags and configuration."""

    key: Mapped[str] = fields.string(length=255, unique=True, nullable=False, index=True)
    value: Mapped[str | None] = fields.text(nullable=True)
