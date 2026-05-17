from __future__ import annotations

import json

from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import SecretStr

from alfred.api.writing import router as writing_router
from alfred.core.exceptions import register_exception_handlers
from alfred.core.settings import settings


def _enable_writing_stub(monkeypatch) -> None:
    # Ensure tests never hit external LLM/network calls even if local env has keys configured.
    monkeypatch.setattr(settings, "alfred_writing_stub", True)


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


def _parse_agui_frames(body: str) -> list[dict]:
    """Parse an AG-UI SSE response body into ordered frame dicts.

    Frames are `id: <seq>\\ndata: <json>\\n\\n` blocks; we extract the JSON
    payload from each data line and ignore the seq id.
    """
    frames: list[dict] = []
    for block in body.split("\n\n"):
        if not block.strip():
            continue
        for line in block.splitlines():
            if line.startswith("data: "):
                frames.append(json.loads(line[len("data: ") :]))
    return frames


def test_writing_stream_emits_canonical_agui_frames(monkeypatch) -> None:
    _enable_writing_stub(monkeypatch)
    client = make_client()
    res = client.post(
        "/api/writing/compose/stream",
        json={"site_url": "https://x.com", "intent": "compose", "instruction": "Say hi"},
    )
    assert res.status_code == 200
    assert "text/event-stream" in res.headers.get("content-type", "")

    frames = _parse_agui_frames(res.text)
    types = [f["type"] for f in frames]

    # Canonical lifecycle ordering.
    assert types[0] == "RUN_STARTED"
    assert types[-1] == "RUN_FINISHED"
    assert "TEXT_MESSAGE_START" in types
    assert "TEXT_MESSAGE_END" in types
    assert "TEXT_MESSAGE_CONTENT" in types

    # Preset metadata is preserved as a CUSTOM frame.
    custom = next(f for f in frames if f["type"] == "CUSTOM")
    assert custom["name"] == "alfred.writing.preset"
    assert custom["value"]["preset"]["key"] == "x"

    # runId and messageId are stable within their respective frames.
    run_ids = {f.get("runId") for f in frames if "runId" in f}
    assert len(run_ids) == 1 and next(iter(run_ids))

    message_ids = {f.get("messageId") for f in frames if "messageId" in f}
    assert len(message_ids) == 1 and next(iter(message_ids))


def test_writing_extension_token_is_enforced_when_configured(monkeypatch) -> None:
    _enable_writing_stub(monkeypatch)
    monkeypatch.setattr(settings, "alfred_extension_token", SecretStr("secret"))
    client = make_client()
    res = client.post("/api/writing/compose", json={"draft": "hello"})
    assert res.status_code == 401

    res2 = client.post(
        "/api/writing/compose",
        json={"draft": "hello"},
        headers={"X-Alfred-Token": "secret"},
    )
    assert res2.status_code == 200
