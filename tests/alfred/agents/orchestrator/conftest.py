"""Shared fixtures for orchestrator tests."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pytest


@dataclass
class FakeZettelCard:
    """Minimal stand-in for ZettelCard ORM object."""

    id: int = 1
    title: str = "Test Card"
    content: str = "Some content"
    summary: str = "A summary"
    topic: str = "testing"
    tags: list[str] = field(default_factory=lambda: ["test"])


class FakeZettelkastenService:
    """In-memory fake of ZettelkastenService for unit tests."""

    def __init__(self) -> None:
        self._cards: dict[int, FakeZettelCard] = {}
        self._next_id = 1

    def list_cards(
        self, *, q: str | None = None, topic: str | None = None, limit: int = 10, **kwargs: Any
    ) -> list[FakeZettelCard]:
        results = list(self._cards.values())
        if q:
            results = [c for c in results if q.lower() in c.title.lower() or q.lower() in c.content.lower()]
        if topic:
            results = [c for c in results if c.topic == topic]
        return results[:limit]

    def create_card(self, data: Any) -> FakeZettelCard:
        card = FakeZettelCard(
            id=self._next_id,
            title=getattr(data, "title", data.get("title", "Untitled")) if isinstance(data, dict) else data.title,
            content=getattr(data, "content", "") if not isinstance(data, dict) else data.get("content", ""),
            tags=getattr(data, "tags", []) if not isinstance(data, dict) else data.get("tags", []),
            topic=getattr(data, "topic", "") if not isinstance(data, dict) else data.get("topic", ""),
        )
        self._cards[card.id] = card
        self._next_id += 1
        return card

    def get_card(self, card_id: int) -> FakeZettelCard | None:
        return self._cards.get(card_id)

    def update_card(self, card_id: int, patch: Any) -> FakeZettelCard | None:
        card = self._cards.get(card_id)
        if not card:
            return None
        if hasattr(patch, "title") and patch.title is not None:
            card.title = patch.title
        if hasattr(patch, "content") and patch.content is not None:
            card.content = patch.content
        if hasattr(patch, "tags") and patch.tags is not None:
            card.tags = patch.tags
        if hasattr(patch, "topic") and patch.topic is not None:
            card.topic = patch.topic
        return card


@pytest.fixture()
def fake_zettel_service() -> FakeZettelkastenService:
    svc = FakeZettelkastenService()
    svc.create_card(FakeZettelCard(title="LangGraph Basics", content="LangGraph is a framework for building agents", topic="ai", tags=["langgraph"]))
    svc.create_card(FakeZettelCard(title="Stoic Philosophy", content="Stoicism teaches virtue and resilience", topic="philosophy", tags=["stoicism"]))
    return svc
