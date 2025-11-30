from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from alfred.api.mind_palace_agent import routes as mp_agent_routes
from alfred.services.agents.mind_palace_agent import KnowledgeAgentService


class _FakeDocStorage:
    def list_documents(self, *, q=None, skip=0, limit=20, **kwargs):  # noqa: ANN001
        return {
            "items": [
                {
                    "id": "doc1",
                    "title": "System Design Basics",
                    "source_url": "https://example.com/sd",
                    "summary": "Basics of system design",
                }
            ],
            "total": 1,
            "skip": skip,
            "limit": limit,
        }


class _EmptyMCP:
    async def health(self):  # noqa: D401
        return True

    async def query(self, query: str, context=None):  # noqa: ANN001, D401
        return {"results": []}


def _app_with_fallback_agent() -> TestClient:
    app = FastAPI()
    app.include_router(mp_agent_routes.router)
    svc = KnowledgeAgentService(doc_service=_FakeDocStorage(), mcp_client=_EmptyMCP())
    app.dependency_overrides[mp_agent_routes.get_agent_service] = lambda: svc
    return TestClient(app)


def test_agent_falls_back_when_mcp_empty():
    client = _app_with_fallback_agent()
    resp = client.post(
        "/api/mind-palace/agent/query",
        json={"question": "system design", "history": [], "context": {}},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["sources"], "Should contain fallback document sources"
    assert data["meta"]["mode"] == "fallback"

