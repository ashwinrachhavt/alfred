from __future__ import annotations

from alfred.api.brand import router as brand_router
from alfred.api.portfolio import router as portfolio_router
from alfred.core.exceptions import register_exception_handlers
from fastapi import FastAPI
from fastapi.testclient import TestClient


def make_client() -> TestClient:
    app = FastAPI()
    register_exception_handlers(app)
    app.include_router(portfolio_router)
    app.include_router(brand_router)
    return TestClient(app)


def test_portfolio_page_renders_without_llm_config() -> None:
    client = make_client()
    res = client.get("/ai")
    assert res.status_code == 200
    assert "text/html" in res.headers.get("content-type", "")
    assert "Portfolio" in res.text


def test_brand_inventory_empty_payload_returns_stub() -> None:
    client = make_client()
    res = client.post("/api/brand/inventory", json={})
    assert res.status_code == 200
    data = res.json()
    assert data["headline"] == "AI Engineer"
    assert data["experiences"] == []


def test_brand_stories_requires_job_description() -> None:
    client = make_client()
    res = client.post("/api/brand/stories", json={"job_description": "too short"})
    assert res.status_code == 422


def test_brand_outreach_requires_profile_context() -> None:
    client = make_client()
    res = client.post("/api/brand/outreach", json={"company": "OpenAI"})
    assert res.status_code == 422
