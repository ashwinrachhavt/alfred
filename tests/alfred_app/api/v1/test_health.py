from fastapi import FastAPI
from fastapi.testclient import TestClient

# Import only the health router to avoid importing incomplete modules.
from alfred_app.api.v1.health import router as health_router


def test_health_endpoint_ok():
    app = FastAPI()
    app.include_router(health_router)
    client = TestClient(app)

    resp = client.get("/healthz")
    assert resp.status_code == 200
    assert resp.json() == {"ok": True}

