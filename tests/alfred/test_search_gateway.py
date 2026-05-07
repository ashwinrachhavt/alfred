from __future__ import annotations

import json

from fastapi.responses import Response
from fastapi.testclient import TestClient

from alfred import search_gateway


def test_health_reports_configured_services(monkeypatch) -> None:
    monkeypatch.setattr(
        search_gateway.settings,
        "search_gateway_firecrawl_url",
        "http://firecrawl:3002/v1",
    )
    monkeypatch.setattr(
        search_gateway.settings,
        "search_gateway_searxng_url",
        "http://searxng:8080",
    )

    async def fake_check(client, url: str) -> str:
        return "up" if "firecrawl" in url or "searxng" in url else "down"

    monkeypatch.setattr(search_gateway, "_check", fake_check)

    client = TestClient(search_gateway.app)
    response = client.get("/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["firecrawl_url"] == "http://firecrawl:3002/v1"
    assert payload["searxng_url"] == "http://searxng:8080"
    assert payload["firecrawl_status"] == "up"
    assert payload["qdrant_status"] == "down"


def test_firecrawl_route_proxies_to_configured_base(monkeypatch) -> None:
    calls = []

    async def fake_proxy(request, base_url: str, path: str) -> Response:
        calls.append((base_url, path, await request.json()))
        return Response(
            json.dumps({"success": True}),
            media_type="application/json",
        )

    monkeypatch.setattr(
        search_gateway.settings,
        "search_gateway_firecrawl_url",
        "http://firecrawl:3002/v1",
    )
    monkeypatch.setattr(search_gateway, "_proxy", fake_proxy)

    client = TestClient(search_gateway.app)
    response = client.post(
        "/firecrawl/scrape",
        json={"url": "https://example.com", "formats": ["markdown"]},
    )

    assert response.status_code == 200
    assert response.json() == {"success": True}
    assert calls == [
        (
            "http://firecrawl:3002/v1",
            "scrape",
            {"url": "https://example.com", "formats": ["markdown"]},
        )
    ]
