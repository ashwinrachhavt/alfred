from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from alfred.api.culture_fit.routes import get_culture_fit_analyzer, router
from alfred.schemas.culture_fit import CultureDimension
from fastapi import FastAPI
from fastapi.testclient import TestClient


def _utcnow() -> datetime:
    return datetime.utcnow().replace(tzinfo=timezone.utc)


class _FakeProfiles:
    def __init__(self) -> None:
        self._id = "507f1f77bcf86cd799439011"
        self._doc: dict[str, Any] | None = None

    def upsert(self, payload):  # noqa: ANN001
        now = _utcnow()
        user_id = (payload.user_id or "").strip() or "default"
        self._doc = {
            "id": self._id,
            "user_id": user_id,
            "profile": {
                "values": {"dimensions": payload.values},
                "notes": payload.notes,
            },
            "created_at": now,
            "updated_at": now,
        }
        return self._id

    def get_by_user_id(self, user_id: str | None):  # noqa: ANN001
        if self._doc is None:
            return None
        uid = (user_id or "").strip() or "default"
        if self._doc["user_id"] != uid:
            return None
        return dict(self._doc)


class _FakeInsights:
    def generate_report(self, company: str, **_kwargs):  # noqa: ANN001
        return {
            "company": company,
            "reviews": [
                {"summary": "Flexible schedule and good work-life balance", "pros": ["ownership"]},
            ],
            "posts": [{"title": "Culture", "excerpt": "Fast-paced but supportive"}],
            "signals": {"culture_keywords": ["ownership", "fast-paced"]},
        }


def _create_app() -> FastAPI:
    app = FastAPI()
    app.include_router(router)

    from alfred.api.culture_fit import routes as culture_routes

    profiles = _FakeProfiles()
    app.dependency_overrides[culture_routes.get_culture_fit_profile_service] = lambda: profiles
    app.dependency_overrides[culture_routes.get_company_insights_service] = lambda: _FakeInsights()
    app.dependency_overrides[get_culture_fit_analyzer] = lambda: culture_routes.CultureFitAnalyzer()
    return app


def test_profile_roundtrip_and_analyze_with_inline_corpus():
    client = TestClient(_create_app())

    resp = client.post(
        "/api/culture-fit/profile",
        json={
            "values": {CultureDimension.work_life_balance.value: 80},
            "notes": "Prefer sustainability.",
        },
    )
    assert resp.status_code == 200

    resp2 = client.get("/api/culture-fit/profile")
    assert resp2.status_code == 200
    assert resp2.json()["user_id"] == "default"

    resp3 = client.post(
        "/api/culture-fit/analyze",
        json={
            "company": "ExampleCo",
            "fetch_company_insights": False,
            "reviews": ["Great work-life balance and flexible hours."],
            "discussions": ["Some micromanagement."],
        },
    )
    assert resp3.status_code == 200
    body = resp3.json()
    assert body["company"] == "ExampleCo"
    assert "fit" in body and "overall" in body["fit"]


def test_analyze_fetches_insights_when_enabled():
    client = TestClient(_create_app())

    client.post(
        "/api/culture-fit/profile",
        json={
            "values": {CultureDimension.pace.value: 30},
        },
    )

    resp = client.post(
        "/api/culture-fit/analyze",
        json={
            "company": "ExampleCo",
            "fetch_company_insights": True,
            "refresh": False,
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["company_profile"]["keywords"]
