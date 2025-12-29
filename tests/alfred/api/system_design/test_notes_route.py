from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from alfred.api import register_routes
from alfred.core.dependencies import get_system_design_service
from alfred.schemas.system_design import ExcalidrawData, SystemDesignSession
from fastapi import FastAPI
from fastapi.testclient import TestClient


@dataclass
class DummySystemDesignService:
    session: SystemDesignSession

    def update_notes(self, session_id: str, notes_markdown: str) -> SystemDesignSession | None:
        if session_id != self.session.id:
            return None
        self.session.notes_markdown = notes_markdown
        return self.session


def test_update_notes_route_returns_session() -> None:
    session = SystemDesignSession(
        id="sess-1",
        share_id="share-1",
        title=None,
        problem_statement="Design X",
        template_id=None,
        notes_markdown="",
        diagram=ExcalidrawData(elements=[], appState={}, files={}, metadata={}),
        versions=[],
        exports=[],
        artifacts={},
        created_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
        updated_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
        metadata={},
    )

    app = FastAPI()
    register_routes(app)
    app.dependency_overrides[get_system_design_service] = lambda: DummySystemDesignService(session)

    client = TestClient(app)
    resp = client.patch(
        "/api/system-design/sessions/sess-1/notes", json={"notes_markdown": "# Hello"}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == "sess-1"
    assert data["notes_markdown"] == "# Hello"
