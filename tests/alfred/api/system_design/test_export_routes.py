from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from fastapi import FastAPI
from fastapi.testclient import TestClient

from alfred.api import register_routes
from alfred.core.dependencies import get_system_design_service
from alfred.schemas.system_design import ExcalidrawData, SystemDesignSession


@dataclass
class DummySystemDesignService:
    session: SystemDesignSession

    def get_session(self, session_id: str) -> SystemDesignSession | None:
        if session_id != self.session.id:
            return None
        return self.session


def test_export_routes_return_valid_code() -> None:
    diagram = ExcalidrawData(
        elements=[
            {"id": "node-1", "type": "rectangle", "label": {"text": "Client"}},
            {"id": "node-2", "type": "rectangle", "label": {"text": "API"}},
            {
                "id": "edge-1",
                "type": "arrow",
                "startBinding": {"elementId": "node-1"},
                "endBinding": {"elementId": "node-2"},
            },
        ],
        appState={},
        files={},
        metadata={},
    )

    session = SystemDesignSession(
        id="sess-1",
        share_id="share-1",
        title="Test",
        problem_statement="Design X",
        template_id=None,
        notes_markdown="",
        diagram=diagram,
        versions=[],
        exports=[],
        artifacts={},
        created_at=datetime(2025, 1, 1, tzinfo=UTC),
        updated_at=datetime(2025, 1, 1, tzinfo=UTC),
        metadata={},
    )

    svc = DummySystemDesignService(session=session)
    app = FastAPI()
    register_routes(app)
    app.dependency_overrides[get_system_design_service] = lambda: svc
    client = TestClient(app)

    mermaid_resp = client.get("/api/system-design/sessions/sess-1/export/mermaid")
    assert mermaid_resp.status_code == 200
    assert mermaid_resp.text.startswith("flowchart")
    assert "Client" in mermaid_resp.text
    assert "API" in mermaid_resp.text

    plantuml_resp = client.get("/api/system-design/sessions/sess-1/export/plantuml")
    assert plantuml_resp.status_code == 200
    assert plantuml_resp.text.startswith("@startuml")
    assert plantuml_resp.text.rstrip().endswith("@enduml")
    assert "Client" in plantuml_resp.text
    assert "API" in plantuml_resp.text

