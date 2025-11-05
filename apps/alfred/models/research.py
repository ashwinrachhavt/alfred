"""Research-related ORM models."""

from __future__ import annotations

from typing import Any

from alfred.models import Mapped, Model, fields


class ResearchRun(Model):
    """Stores successful deep research executions."""

    query: Mapped[str] = fields.text(nullable=False)
    target_length_words: Mapped[int] = fields.integer(nullable=False)
    tone: Mapped[str] = fields.string(length=32, nullable=False)
    article: Mapped[str] = fields.text(nullable=False)
    state: Mapped[dict[str, Any]] = fields.json(nullable=False)
