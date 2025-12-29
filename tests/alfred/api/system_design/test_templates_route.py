from __future__ import annotations

from alfred.api import register_routes
from alfred.core.dependencies import get_system_design_service
from alfred.schemas.system_design import TemplateDefinition
from fastapi import FastAPI
from fastapi.testclient import TestClient


class DummySystemDesignService:
    def template_library(self) -> list[TemplateDefinition]:
        return []


def create_app() -> FastAPI:
    app = FastAPI()
    register_routes(app)
    app.dependency_overrides[get_system_design_service] = lambda: DummySystemDesignService()
    return app


def test_system_design_templates_route_is_registered_and_callable() -> None:
    app = create_app()
    assert any(
        getattr(route, "path", None) == "/api/system-design/library/templates"
        for route in app.routes
    )

    client = TestClient(app)
    resp = client.get("/api/system-design/library/templates")
    assert resp.status_code == 200
    assert resp.json() == []
