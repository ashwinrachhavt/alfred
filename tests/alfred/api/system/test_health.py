from alfred.api.system import router as system_router
from fastapi import FastAPI
from fastapi.testclient import TestClient


def create_app() -> FastAPI:
    app = FastAPI()
    app.include_router(system_router)
    return app


def test_healthz_ok():
    client = TestClient(create_app())
    resp = client.get("/healthz")
    assert resp.status_code == 200
    assert resp.json() == {"ok": True}
