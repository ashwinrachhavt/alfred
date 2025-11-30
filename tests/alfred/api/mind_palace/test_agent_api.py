from __future__ import annotations

from alfred.api.mind_palace_agent import routes as mp_agent_routes
from fastapi import FastAPI
from fastapi.testclient import TestClient


class _FakeAgent:
    async def ask(self, *, question: str, history=None, context=None):  # noqa: ANN001
        return {
            "answer": f"You asked: {question}",
            "sources": [
                {"title": "Doc A", "source_url": "https://example.com/a"},
            ],
            "meta": {"mode": "test"},
        }


def _app_with_fake_agent() -> TestClient:
    app = FastAPI()
    app.include_router(mp_agent_routes.router)
    app.dependency_overrides[mp_agent_routes.get_agent_service] = lambda: _FakeAgent()
    return TestClient(app)


def test_agent_query_endpoint():
    client = _app_with_fake_agent()
    resp = client.post(
        "/api/mind-palace/agent/query",
        json={"question": "Find design patterns", "history": [], "context": {}},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["answer"].startswith("You asked:")
    assert data["sources"][0]["title"] == "Doc A"
    assert data["meta"]["mode"] == "test"
