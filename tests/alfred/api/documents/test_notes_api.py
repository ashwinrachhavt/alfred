from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from alfred.api.documents import routes as doc_routes
from fastapi import FastAPI
from fastapi.testclient import TestClient


class _FakeDocStorage:
    def __init__(self) -> None:
        self._notes: Dict[str, Dict[str, Any]] = {}
        self._next_id = 1

    # API used by routes
    def create_note(self, note) -> str:  # noqa: ANN001 - schema type comes from app
        note_id = str(self._next_id)
        self._next_id += 1
        now = datetime.now(tz=timezone.utc)
        self._notes[note_id] = {
            "id": note_id,
            "text": note.text,
            "source_url": note.source_url,
            "metadata": note.metadata or {},
            "created_at": now,
        }
        return note_id

    def get_note(self, note_id: str) -> Optional[Dict[str, Any]]:
        return self._notes.get(note_id)

    def list_notes(self, *, q: Optional[str], skip: int, limit: int) -> Dict[str, Any]:
        items: List[Dict[str, Any]] = list(self._notes.values())
        if q:
            q_lower = q.lower()
            items = [i for i in items if q_lower in (i.get("text") or "").lower()]
        items_sorted = sorted(items, key=lambda x: x["created_at"], reverse=True)
        window = items_sorted[skip : skip + limit]
        return {"items": window, "total": len(items), "skip": skip, "limit": limit}


def _app_with_fake_service() -> TestClient:
    app = FastAPI()
    app.include_router(doc_routes.router)

    fake = _FakeDocStorage()

    # Override dependency to use fake service
    app.dependency_overrides[doc_routes.get_doc_storage_service] = lambda: fake

    return TestClient(app)


def test_create_note_happy_path():
    client = _app_with_fake_service()
    resp = client.post(
        "/api/documents/notes",
        json={"text": "hello world", "source_url": "https://example.com"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["text"] == "hello world"
    assert data["source_url"] == "https://example.com"
    assert isinstance(data["id"], str)
    assert data["id"]
    assert data["metadata"] == {}


def test_create_note_validation_error():
    client = _app_with_fake_service()
    resp = client.post("/api/documents/notes", json={"text": "   "})
    # Validation occurs at request model parsing (422)
    assert resp.status_code == 422


def test_list_notes_basic_pagination_and_filtering():
    client = _app_with_fake_service()
    client.post("/api/documents/notes", json={"text": "alpha"})
    client.post("/api/documents/notes", json={"text": "beta"})
    client.post("/api/documents/notes", json={"text": "alphabet"})

    resp = client.get("/api/documents/notes", params={"q": "alp", "skip": 0, "limit": 10})
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 2
    assert len(data["items"]) == 2
    texts = [item["text"] for item in data["items"]]
    assert set(texts) == {"alpha", "alphabet"}
