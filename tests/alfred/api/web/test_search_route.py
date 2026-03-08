from fastapi import FastAPI
from fastapi.testclient import TestClient

from alfred.api.web import routes as web_routes


def create_app() -> FastAPI:
    app = FastAPI()
    app.include_router(web_routes.router)
    return app


def test_web_search_route_respects_payload(monkeypatch):
    def fake_search_web(**kwargs):
        return {
            "provider": "searx",
            "query": kwargs.get("q"),
            "hits": [{"title": "A", "url": "http://a", "snippet": "s", "source": "exa"}],
            "meta": {"ok": True},
        }

    monkeypatch.setattr(web_routes, "search_web", fake_search_web)
    client = TestClient(create_app())
    resp = client.get(
        "/api/web/search",
        params={"q": "hello", "searx_k": 7, "categories": "general"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["provider"] == "searx"
    assert data["query"] == "hello"
    assert data["meta"]["ok"] is True
    assert data["hits"] and data["hits"][0]["url"] == "http://a"
