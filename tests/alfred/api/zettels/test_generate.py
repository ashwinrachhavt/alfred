from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from alfred.api.dependencies import get_db_session
from alfred.api.zettels.routes import router as zettels_router


def _make_card() -> SimpleNamespace:
    now = datetime.now(tz=UTC)
    return SimpleNamespace(
        id=123,
        title="Generated card",
        content="Generated content",
        summary="Generated summary",
        tags=["ai", "prompt"],
        topic="knowledge",
        source_url=None,
        document_id=None,
        importance=5,
        confidence=0.7,
        status="active",
        created_at=now,
        updated_at=now,
    )


@pytest.fixture()
def client() -> TestClient:
    app = FastAPI()
    app.include_router(zettels_router)
    app.dependency_overrides[get_db_session] = lambda: MagicMock()
    return TestClient(app)


def test_generate_card_accepts_large_prompt_payload(client: TestClient, monkeypatch) -> None:
    seen: dict[str, object] = {}

    def _fake_generate(self, *, prompt=None, content=None, topic=None, tags=None):
        seen["prompt"] = prompt
        seen["content"] = content
        seen["topic"] = topic
        seen["tags"] = tags
        return _make_card()

    monkeypatch.setattr(
        "alfred.api.zettels.routes.ZettelkastenService.generate_card_from_ai",
        _fake_generate,
    )

    large_prompt = "Prompt context " * 800

    response = client.post(
        "/api/zettels/cards/generate",
        json={"prompt": large_prompt, "topic": "knowledge", "tags": ["ai"]},
    )

    assert response.status_code == 201
    assert seen["prompt"] == large_prompt
    assert seen["content"] is None
    assert seen["topic"] == "knowledge"
    assert seen["tags"] == ["ai"]


def test_generate_card_accepts_large_content_payload(client: TestClient, monkeypatch) -> None:
    seen: dict[str, object] = {}

    def _fake_generate(self, *, prompt=None, content=None, topic=None, tags=None):
        seen["prompt"] = prompt
        seen["content"] = content
        return _make_card()

    monkeypatch.setattr(
        "alfred.api.zettels.routes.ZettelkastenService.generate_card_from_ai",
        _fake_generate,
    )

    large_content = "Source paragraph.\n" * 2500

    response = client.post(
        "/api/zettels/cards/generate",
        json={"content": large_content},
    )

    assert response.status_code == 201
    assert seen["prompt"] is None
    assert seen["content"] == large_content
