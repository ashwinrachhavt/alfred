from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import SecretStr

from alfred.api.canvas.routes import _extract_mermaid, router
from alfred.core.settings import settings


class _FakeCompletions:
    def __init__(self) -> None:
        self.requests: list[dict[str, Any]] = []

    async def create(self, **kwargs: Any) -> SimpleNamespace:
        self.requests.append(kwargs)
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(content='{"mermaid":"flowchart TD\\nA-->B"}')
                )
            ]
        )


class _FakeOpenAIClient:
    def __init__(self) -> None:
        self.completions = _FakeCompletions()
        self.chat = SimpleNamespace(completions=self.completions)


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_extract_mermaid_accepts_json_object() -> None:
    assert _extract_mermaid('{"mermaid":"flowchart TD\\nA-->B"}') == "flowchart TD\nA-->B"


def test_generate_mermaid_uses_backend_openai_config(monkeypatch) -> None:
    fake_client = _FakeOpenAIClient()
    monkeypatch.setattr(settings, "openai_api_key", SecretStr("test-key"))
    monkeypatch.setattr(settings, "openai_base_url", None)
    monkeypatch.setattr(settings, "canvas_diagram_model", "gpt-4o")
    monkeypatch.setattr(
        "alfred.core.llm_factory.get_async_openai_client",
        lambda: fake_client,
    )

    response = _client().post(
        "/api/canvas/generate-mermaid",
        json={
            "prompt": "Map a signup flow",
            "canvasTitle": "Growth",
            "canvasContext": "Visible labels: Landing, Signup",
        },
    )

    assert response.status_code == 200
    assert response.json() == {"mermaid": "flowchart TD\nA-->B"}
    request = fake_client.completions.requests[0]
    assert request["model"] == "gpt-4o"
    assert request["response_format"] == {"type": "json_object"}
    assert request["temperature"] == 0.2
    user_message = request["messages"][1]["content"]
    assert "Canvas title:\nGrowth" in user_message
    assert "Visible labels: Landing, Signup" in user_message
