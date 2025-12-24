from __future__ import annotations

from typing import Any

import pytest
from alfred.connectors.web_connector import LangsearchClient
from alfred.core.settings import settings


class _FakeResponse:
    def __init__(self) -> None:
        self._payload = {
            "data": {
                "webPages": {
                    "value": [
                        {
                            "name": "Example",
                            "url": "https://example.com",
                            "snippet": "Snippet",
                            "summary": "Summary",
                        }
                    ]
                }
            }
        }

    def raise_for_status(self) -> None:
        return

    def json(self) -> dict[str, Any]:
        return self._payload


class _FakeClient:
    def __init__(self, *, on_post):  # noqa: ANN001
        self._on_post = on_post

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):  # noqa: ANN001
        return False

    def post(self, url: str, *, json: dict[str, Any], headers: dict[str, str]):  # noqa: A002
        self._on_post(url, json, headers)
        return _FakeResponse()


class _FakeHttpx:
    def __init__(self, *, on_post):  # noqa: ANN001
        self._on_post = on_post

    def Client(self, *, timeout: float):  # noqa: N802, ANN001
        _ = timeout
        return _FakeClient(on_post=self._on_post)


def test_langsearch_client_uses_base_url_and_query_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "langsearch_api_key", "test-key")
    monkeypatch.setattr(settings, "langsearch_base_url", "https://api.langsearch.com/v1/web-search")

    client = LangsearchClient()

    seen: dict[str, Any] = {}

    def on_post(url: str, payload: dict[str, Any], headers: dict[str, str]) -> None:
        seen["url"] = url
        seen["payload"] = payload
        seen["headers"] = headers

    client._httpx = _FakeHttpx(on_post=on_post)  # type: ignore[attr-defined]

    resp = client.search("hello", count=50)

    assert resp.provider == "langsearch"
    assert resp.hits and resp.hits[0].url == "https://example.com"
    assert seen["url"] == "https://api.langsearch.com/v1/web-search"
    assert seen["payload"]["query"] == "hello"
    assert seen["payload"]["count"] == 10  # clamped
    assert "Authorization" in seen["headers"]
