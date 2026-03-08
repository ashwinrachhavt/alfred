from __future__ import annotations

from datetime import UTC, datetime

from fastapi import FastAPI
from fastapi.testclient import TestClient

from alfred.api import register_routes
from alfred.core.dependencies import get_system_design_service
from alfred.schemas.system_design import SystemDesignSessionSummary


class DummySystemDesignService:
    def list_sessions(self, *, limit: int = 20) -> list[SystemDesignSessionSummary]:
        sessions = [
            SystemDesignSessionSummary(
                id="sess-1",
                share_id="share-1",
                title="Design X",
                problem_statement="Design X",
                template_id=None,
                version=3,
                created_at=datetime(2025, 1, 1, tzinfo=UTC),
                updated_at=datetime(2025, 1, 2, tzinfo=UTC),
            )
        ]
        return sessions[:limit]


def test_system_design_list_sessions_route_returns_summaries() -> None:
    app = FastAPI()
    register_routes(app)
    app.dependency_overrides[get_system_design_service] = lambda: DummySystemDesignService()

    client = TestClient(app)
    resp = client.get("/api/system-design/sessions?limit=5")
    assert resp.status_code == 200
    payload = resp.json()
    assert isinstance(payload, list)
    assert payload[0]["id"] == "sess-1"
    assert payload[0]["share_id"] == "share-1"
    assert payload[0]["title"] == "Design X"
    assert payload[0]["problem_statement"] == "Design X"
    assert payload[0]["template_id"] is None
    assert payload[0]["version"] == 3
    assert payload[0]["created_at"].startswith("2025-01-01T00:00:00")
    assert payload[0]["updated_at"].startswith("2025-01-02T00:00:00")
