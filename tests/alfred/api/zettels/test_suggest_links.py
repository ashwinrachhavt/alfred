from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from alfred.api.dependencies import get_db_session
from alfred.api.zettels.routes import router as zettels_router


@pytest.fixture()
def client() -> TestClient:
    app = FastAPI()
    app.include_router(zettels_router)
    app.dependency_overrides[get_db_session] = lambda: MagicMock()
    return TestClient(app)


def test_suggest_links_returns_empty_list_when_backend_unavailable(client, monkeypatch) -> None:
    def _failing_suggest_links(self, *, card_id: int, min_confidence: float, limit: int):
        raise RuntimeError("qdrant unavailable")

    monkeypatch.setattr(
        "alfred.api.zettels.routes.ZettelkastenService.suggest_links",
        _failing_suggest_links,
    )

    response = client.post("/api/zettels/cards/118/suggest-links?min_confidence=0.4&limit=8")

    assert response.status_code == 200
    assert response.json() == []


def test_suggest_links_still_returns_404_for_missing_card(client, monkeypatch) -> None:
    def _missing_card(self, *, card_id: int, min_confidence: float, limit: int):
        raise ValueError("Card not found")

    monkeypatch.setattr(
        "alfred.api.zettels.routes.ZettelkastenService.suggest_links",
        _missing_card,
    )

    response = client.post("/api/zettels/cards/999/suggest-links")

    assert response.status_code == 404
    assert response.json()["detail"] == "Card not found"
