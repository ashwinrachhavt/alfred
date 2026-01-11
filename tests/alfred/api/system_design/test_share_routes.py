from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.testclient import TestClient

from alfred.api import register_routes
from alfred.core.dependencies import get_system_design_service
from alfred.schemas.system_design import ExcalidrawData, SystemDesignSession


@dataclass
class DummySystemDesignService:
    session: SystemDesignSession
    last_share_id: str | None = None
    last_share_password: str | None = None
    last_share_enabled: bool | None = None

    def get_shared_session(self, share_id: str, *, password: str | None = None) -> SystemDesignSession:
        self.last_share_id = share_id
        self.last_share_password = password
        return self.session

    def update_share_settings(self, session_id: str, payload):  # type: ignore[no-untyped-def]
        self.last_share_enabled = payload.enabled
        return self.session


def test_shared_session_route_forwards_password_header() -> None:
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

    svc = DummySystemDesignService(session=session)
    app = FastAPI()
    register_routes(app)
    app.dependency_overrides[get_system_design_service] = lambda: svc
    client = TestClient(app)

    resp = client.get("/api/system-design/sessions/share/share-1")
    assert resp.status_code == 200
    assert svc.last_share_password is None

    resp = client.get(
        "/api/system-design/sessions/share/share-1", headers={"X-Alfred-Share-Password": "secret"}
    )
    assert resp.status_code == 200
    assert svc.last_share_password == "secret"


def test_update_share_settings_route_calls_service() -> None:
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

    svc = DummySystemDesignService(session=session)
    app = FastAPI()
    register_routes(app)
    app.dependency_overrides[get_system_design_service] = lambda: svc
    client = TestClient(app)

    resp = client.patch("/api/system-design/sessions/sess-1/share", json={"enabled": False})
    assert resp.status_code == 200
    assert svc.last_share_enabled is False

