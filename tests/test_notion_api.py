from __future__ import annotations

from alfred.api.notion import router as notion_router
from alfred.core.exceptions import register_exception_handlers
from fastapi import FastAPI
from fastapi.testclient import TestClient


def make_client() -> TestClient:
    app = FastAPI()
    register_exception_handlers(app)
    app.include_router(notion_router)
    return TestClient(app)


def test_notion_search_returns_results(monkeypatch) -> None:
    def _stub_search_pages(query: str, page_size: int = 25):
        assert query == "hello"
        assert page_size == 2
        return [
            {
                "page_id": "page-1",
                "title": "Hello",
                "url": "https://notion.so/page-1",
                "last_edited_time": "2026-01-10T00:00:00Z",
            }
        ]

    monkeypatch.setattr("alfred.services.notion.search_pages", _stub_search_pages)

    client = make_client()
    res = client.get("/api/notion/search?q=hello&limit=2")
    assert res.status_code == 200
    data = res.json()
    assert data["results"][0]["page_id"] == "page-1"
    assert data["results"][0]["title"] == "Hello"


def test_notion_page_markdown_returns_payload(monkeypatch) -> None:
    def _stub_get_page_markdown(page_id: str):
        assert page_id == "page-123"
        return {
            "page_id": page_id,
            "title": "Test Page",
            "url": "https://notion.so/page-123",
            "last_edited_time": "2026-01-10T00:00:00Z",
            "markdown": "# Hello\n\nWorld",
        }

    monkeypatch.setattr("alfred.services.notion.get_page_markdown", _stub_get_page_markdown)

    client = make_client()
    res = client.get("/api/notion/pages/page-123/markdown")
    assert res.status_code == 200
    data = res.json()
    assert data["page_id"] == "page-123"
    assert data["markdown"].startswith("# Hello")


def test_notion_page_markdown_update_calls_service(monkeypatch) -> None:
    calls = []

    def _stub_update_page_markdown(*, page_id: str, markdown: str, mode: str):
        calls.append((page_id, markdown, mode))
        return {"ok": True}

    monkeypatch.setattr("alfred.services.notion.update_page_markdown", _stub_update_page_markdown)

    client = make_client()
    res = client.post(
        "/api/notion/pages/page-999/markdown",
        json={"markdown": "# Updated", "mode": "replace"},
    )
    assert res.status_code == 200
    assert res.json()["success"] is True
    assert calls == [("page-999", "# Updated", "replace")]
