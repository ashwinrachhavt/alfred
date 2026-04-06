"""Tests for POST /api/zettels/cards/bulk endpoint."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from alfred.api.dependencies import get_db_session
from alfred.api.zettels.routes import router as zettels_router

# --------------- Helpers ---------------


def _make_card(card_id: int, **overrides: Any) -> MagicMock:
    """Create a mock ZettelCard with sensible defaults."""
    now = datetime.now(tz=UTC)
    card = MagicMock()
    card.id = card_id
    card.title = overrides.get("title", f"Card {card_id}")
    card.content = overrides.get("content", None)
    card.summary = overrides.get("summary", None)
    card.tags = overrides.get("tags", [])
    card.topic = overrides.get("topic", None)
    card.source_url = overrides.get("source_url", None)
    card.document_id = overrides.get("document_id", None)
    card.importance = overrides.get("importance", 0)
    card.confidence = overrides.get("confidence", 0.0)
    card.status = overrides.get("status", "active")
    card.created_at = overrides.get("created_at", now)
    card.updated_at = overrides.get("updated_at", now)

    # Make model_validate work with ZettelCardOut
    card.__class__.__name__ = "ZettelCard"

    return card


class FakeZettelkastenService:
    """Fake service that records calls and returns mock cards."""

    def __init__(self) -> None:
        self.batch_calls: list[list[dict]] = []
        self._next_id = 1

    def create_cards_batch(self, cards_data: list[dict]) -> list[MagicMock]:
        self.batch_calls.append(cards_data)
        result = []
        for data in cards_data:
            card = _make_card(self._next_id, **data)
            self._next_id += 1
            result.append(card)
        return result


def _create_app(fake_session: Any = None) -> FastAPI:
    app = FastAPI()
    app.include_router(zettels_router)

    if fake_session is not None:
        app.dependency_overrides[get_db_session] = lambda: fake_session

    return app


@pytest.fixture()
def fake_svc():
    return FakeZettelkastenService()


@pytest.fixture()
def client(fake_svc, monkeypatch):
    """TestClient with ZettelkastenService patched."""
    fake_session = MagicMock()
    app = _create_app(fake_session)

    def _patched_init(self, session):
        # Redirect all service method calls to our fake
        self.session = session
        self.create_cards_batch = fake_svc.create_cards_batch

    monkeypatch.setattr(
        "alfred.api.zettels.routes.ZettelkastenService.__init__",
        _patched_init,
    )

    return TestClient(app)


# --------------- Tests ---------------


class TestBulkCreateHappyPath:
    def test_creates_multiple_cards(self, client, fake_svc):
        payload = [
            {"title": "Card A"},
            {"title": "Card B"},
            {"title": "Card C"},
        ]
        resp = client.post("/api/zettels/cards/bulk", json=payload)

        assert resp.status_code == 201
        data = resp.json()
        assert len(data) == 3
        assert data[0]["title"] == "Card A"
        assert data[1]["title"] == "Card B"
        assert data[2]["title"] == "Card C"

    def test_returns_card_ids(self, client, fake_svc):
        payload = [{"title": "Test Card"}]
        resp = client.post("/api/zettels/cards/bulk", json=payload)

        assert resp.status_code == 201
        data = resp.json()
        assert len(data) == 1
        assert isinstance(data[0]["id"], int)

    def test_passes_optional_fields(self, client, fake_svc):
        payload = [
            {
                "title": "With Topic",
                "topic": "distributed-systems",
                "tags": ["cap", "consensus"],
                "importance": 7,
            }
        ]
        resp = client.post("/api/zettels/cards/bulk", json=payload)

        assert resp.status_code == 201
        assert len(fake_svc.batch_calls) == 1
        batch = fake_svc.batch_calls[0]
        assert batch[0]["topic"] == "distributed-systems"
        assert batch[0]["tags"] == ["cap", "consensus"]
        assert batch[0]["importance"] == 7


class TestBulkCreateValidation:
    def test_rejects_empty_payload(self, client):
        resp = client.post("/api/zettels/cards/bulk", json=[])
        assert resp.status_code == 400
        assert "At least one card" in resp.json()["detail"]

    def test_rejects_over_50_cards(self, client):
        payload = [{"title": f"Card {i}"} for i in range(51)]
        resp = client.post("/api/zettels/cards/bulk", json=payload)
        assert resp.status_code == 400
        assert "Maximum 50" in resp.json()["detail"]

    def test_rejects_missing_title(self, client):
        """Cards without a title should fail Pydantic validation."""
        resp = client.post("/api/zettels/cards/bulk", json=[{"content": "no title"}])
        assert resp.status_code == 422

    def test_rejects_empty_title(self, client):
        """Empty string title should fail min_length validation."""
        resp = client.post("/api/zettels/cards/bulk", json=[{"title": ""}])
        assert resp.status_code == 422

    def test_accepts_exactly_50_cards(self, client, fake_svc):
        payload = [{"title": f"Card {i}"} for i in range(50)]
        resp = client.post("/api/zettels/cards/bulk", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert len(data) == 50
