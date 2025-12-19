from alfred.core.exceptions import ConfigurationError, RateLimitError, register_exception_handlers
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient


def create_app() -> FastAPI:
    app = FastAPI()
    register_exception_handlers(app)

    @app.get("/boom")
    def _boom() -> None:
        raise RuntimeError("kaboom")

    @app.get("/config")
    def _config() -> None:
        raise ConfigurationError("missing setting", code="missing_setting")

    @app.get("/rate")
    def _rate() -> None:
        raise RateLimitError("too many requests")

    @app.get("/http")
    def _http() -> None:
        raise HTTPException(status_code=404, detail="not found")

    @app.get("/needs-int")
    def _needs_int(x: int) -> dict[str, int]:
        return {"x": x}

    return app


def test_alfred_exception_handler_shape_and_status():
    client = TestClient(create_app())
    resp = client.get("/config")
    assert resp.status_code == 500
    data = resp.json()
    assert data["error"] == "missing setting"
    assert data["code"] == "missing_setting"
    assert data["type"] == "ConfigurationError"


def test_rate_limit_error_maps_to_429():
    client = TestClient(create_app())
    resp = client.get("/rate")
    assert resp.status_code == 429
    data = resp.json()
    assert data["error"] == "too many requests"
    assert data["code"] == "rate_limited"
    assert data["type"] == "RateLimitError"


def test_http_exception_is_normalized():
    client = TestClient(create_app())
    resp = client.get("/http")
    assert resp.status_code == 404
    data = resp.json()
    assert data["error"] == "not found"
    assert data["code"] == "http_exception"
    assert data["type"] == "HTTPException"


def test_validation_errors_are_normalized():
    client = TestClient(create_app())
    resp = client.get("/needs-int")
    assert resp.status_code == 422
    data = resp.json()
    assert data["error"] == "Validation error"
    assert data["code"] == "validation_error"
    assert data["type"] == "RequestValidationError"
    assert isinstance(data["details"], list)


def test_unhandled_exceptions_are_normalized_and_do_not_leak_message():
    client = TestClient(create_app(), raise_server_exceptions=False)
    resp = client.get("/boom")
    assert resp.status_code == 500
    data = resp.json()
    assert data["error"] == "Internal server error"
    assert data["code"] == "internal_error"
    assert data["type"] == "InternalServerError"
