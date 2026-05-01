"""Contract tests — pin the response shape of the existing today routes.

These exist to prevent drift. If a future change adds, removes or renames a
field on ``TodayBriefingResponse`` or ``TodayCalendarResponse`` (or their
nested models), these tests fail loudly so the author is forced to confirm
the API contract change is intentional.
"""

from __future__ import annotations

from typing import get_type_hints

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from alfred.api.today import routes as today_routes
from alfred.schemas.today import (
    TodayBriefingResponse,
    TodayBriefingStats,
    TodayCalendarDay,
    TodayCalendarResponse,
    TodayCaptureItem,
    TodayConnectionItem,
    TodayGapItem,
    TodayReviewItem,
    TodayStoredCardItem,
)

# ---------------------------------------------------------------------------
# Schema shape pins (no network, pure introspection)
# ---------------------------------------------------------------------------


def _field_names(model) -> set[str]:
    return set(model.model_fields.keys())


def test_briefing_response_top_level_shape_unchanged() -> None:
    """Every field declared on :class:`TodayBriefingResponse` is pinned."""
    assert _field_names(TodayBriefingResponse) == {
        "date",
        "timezone",
        "generated_at",
        "captures",
        "stored_cards",
        "connections",
        "reviews",
        "gaps",
        "stats",
    }


def test_briefing_response_nested_model_types_unchanged() -> None:
    hints = get_type_hints(TodayBriefingResponse)
    assert hints["captures"] == list[TodayCaptureItem]
    assert hints["stored_cards"] == list[TodayStoredCardItem]
    assert hints["connections"] == list[TodayConnectionItem]
    assert hints["reviews"] == list[TodayReviewItem]
    assert hints["gaps"] == list[TodayGapItem]
    assert hints["stats"] is TodayBriefingStats


def test_briefing_stats_shape_unchanged() -> None:
    assert _field_names(TodayBriefingStats) == {
        "total_captures",
        "total_cards_created",
        "total_connections",
        "total_reviews_due",
        "total_reviews_completed",
        "total_gaps",
        "total_events",
        "total_cards",
        "total_links",
    }


def test_capture_item_shape_unchanged() -> None:
    assert _field_names(TodayCaptureItem) == {
        "id",
        "title",
        "source_url",
        "pipeline_status",
        "content_type",
        "created_at",
    }


def test_stored_card_item_shape_unchanged() -> None:
    assert _field_names(TodayStoredCardItem) == {
        "card_id",
        "title",
        "topic",
        "status",
        "tags",
        "created_at",
    }


def test_connection_item_shape_unchanged() -> None:
    assert _field_names(TodayConnectionItem) == {
        "link_id",
        "from_card_id",
        "from_title",
        "to_card_id",
        "to_title",
        "type",
        "created_at",
    }


def test_review_item_shape_unchanged() -> None:
    assert _field_names(TodayReviewItem) == {
        "review_id",
        "card_id",
        "card_title",
        "stage",
        "due_at",
        "completed_at",
        "status",
    }


def test_gap_item_shape_unchanged() -> None:
    assert _field_names(TodayGapItem) == {
        "card_id",
        "title",
        "created_at",
    }


def test_calendar_response_shape_unchanged() -> None:
    assert _field_names(TodayCalendarResponse) == {
        "start_date",
        "end_date",
        "timezone",
        "days",
    }
    assert get_type_hints(TodayCalendarResponse)["days"] == list[TodayCalendarDay]


def test_calendar_day_shape_unchanged() -> None:
    """Spec pin per T3: date, captures, stored_cards, connections,
    reviews_due, reviews_completed, gaps, total_events."""
    assert _field_names(TodayCalendarDay) == {
        "date",
        "captures",
        "stored_cards",
        "connections",
        "reviews_due",
        "reviews_completed",
        "gaps",
        "total_events",
    }


# ---------------------------------------------------------------------------
# End-to-end: briefing & calendar endpoints serialize to the pinned shape
# ---------------------------------------------------------------------------


@pytest.fixture()
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    """Mock the two Celery-land builders so we don't need a DB / Redis."""

    stub_briefing = TodayBriefingResponse(
        date="2026-04-30",
        timezone="UTC",
        generated_at="2026-04-30T00:00:00+00:00",
        stats=TodayBriefingStats(),
    )
    stub_calendar = TodayCalendarResponse(
        start_date="2026-01-01",
        end_date="2026-04-30",
        timezone="UTC",
        days=[TodayCalendarDay(date="2026-04-30")],
    )

    def _fake_build_daily_briefing(*_args, **_kwargs):
        return stub_briefing

    def _fake_build_today_calendar(*_args, **_kwargs):
        return stub_calendar

    import alfred.tasks.daily_briefing as db_mod

    monkeypatch.setattr(db_mod, "build_daily_briefing", _fake_build_daily_briefing)
    monkeypatch.setattr(db_mod, "build_today_calendar", _fake_build_today_calendar)

    app = FastAPI()
    app.include_router(today_routes.router)
    return TestClient(app)


def test_briefing_endpoint_returns_pinned_shape(client: TestClient) -> None:
    resp = client.get("/api/today/briefing")
    assert resp.status_code == 200
    body = resp.json()
    assert set(body.keys()) >= {
        "date",
        "timezone",
        "generated_at",
        "captures",
        "stored_cards",
        "connections",
        "reviews",
        "gaps",
        "stats",
    }
    assert set(body["stats"].keys()) >= {
        "total_captures",
        "total_cards_created",
        "total_connections",
        "total_reviews_due",
        "total_reviews_completed",
        "total_gaps",
        "total_events",
        "total_cards",
        "total_links",
    }


def test_calendar_endpoint_returns_pinned_shape(client: TestClient) -> None:
    resp = client.get("/api/today/calendar")
    assert resp.status_code == 200
    body = resp.json()
    assert set(body.keys()) >= {"start_date", "end_date", "timezone", "days"}
    assert body["days"], "fixture guarantees at least one day in the response"
    day = body["days"][0]
    assert set(day.keys()) >= {
        "date",
        "captures",
        "stored_cards",
        "connections",
        "reviews_due",
        "reviews_completed",
        "gaps",
        "total_events",
    }
