from __future__ import annotations

from alfred.api.writing import router as writing_router
from alfred.core.exceptions import register_exception_handlers
from fastapi import FastAPI
from fastapi.testclient import TestClient


def _enable_writing_stub(monkeypatch) -> None:
    # Ensure tests never hit external LLM/network calls even if local env has keys configured.
    monkeypatch.setenv("ALFRED_WRITING_STUB", "1")


def make_client() -> TestClient:
    app = FastAPI()
    register_exception_handlers(app)
    app.include_router(writing_router)
    return TestClient(app)


def test_writing_presets_lists_generic(monkeypatch) -> None:
    _enable_writing_stub(monkeypatch)
    client = make_client()
    res = client.get("/api/writing/presets")
    assert res.status_code == 200
    data = res.json()
    assert any(p.get("key") == "generic" for p in data)


def test_writing_compose_returns_stub_without_llm_config(monkeypatch) -> None:
    _enable_writing_stub(monkeypatch)
    client = make_client()
    res = client.post(
        "/api/writing/compose",
        json={"site_url": "https://linkedin.com", "intent": "rewrite", "draft": "hello"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["preset_used"]["key"] == "linkedin"
    assert data["output"] == "hello"


def test_writing_stream_is_sse_and_contains_events(monkeypatch) -> None:
    _enable_writing_stub(monkeypatch)
    client = make_client()
    res = client.post(
        "/api/writing/compose/stream",
        json={"site_url": "https://x.com", "intent": "compose", "instruction": "Say hi"},
    )
    assert res.status_code == 200
    assert "text/event-stream" in res.headers.get("content-type", "")
    body = res.text
    assert "event: meta" in body
    assert "event: token" in body
    assert "event: done" in body


def test_writing_extension_token_is_enforced_when_configured(monkeypatch) -> None:
    _enable_writing_stub(monkeypatch)
    monkeypatch.setenv("ALFRED_EXTENSION_TOKEN", "secret")
    client = make_client()
    res = client.post("/api/writing/compose", json={"draft": "hello"})
    assert res.status_code == 401

    res2 = client.post(
        "/api/writing/compose",
        json={"draft": "hello"},
        headers={"X-Alfred-Token": "secret"},
    )
    assert res2.status_code == 200
