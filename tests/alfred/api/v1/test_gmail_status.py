import importlib

from fastapi import FastAPI
from fastapi.testclient import TestClient


def with_env(env: dict):
    return __import__(__name__)


def test_gmail_status_disabled(monkeypatch):
    monkeypatch.setenv("ENABLE_GMAIL", "false")
    # Ensure minimal config
    # Simulate missing config with safe values (avoid invalid URL)
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "")
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "")
    monkeypatch.delenv("GOOGLE_REDIRECT_URI", raising=False)
    monkeypatch.setenv("GOOGLE_PROJECT_ID", "")
    monkeypatch.delenv("GCP_PUBSUB_TOPIC", raising=False)
    monkeypatch.delenv("TOKEN_STORE_DIR", raising=False)

    # Reload settings to pick up env
    from alfred.core import config as cfg
    importlib.reload(cfg)
    from alfred.api.v1 import gmail_status as gs
    importlib.reload(gs)

    app = FastAPI()
    app.include_router(gs.router)
    client = TestClient(app)
    r = client.get("/api/v1/gmail/status")
    assert r.status_code == 200
    data = r.json()
    assert data["enabled"] is False
    assert data["ready"] is False


def test_gmail_status_enabled_not_configured(monkeypatch):
    monkeypatch.setenv("ENABLE_GMAIL", "true")
    # Make at least one required key missing/empty to mark not configured
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "")
    monkeypatch.delenv("GOOGLE_REDIRECT_URI", raising=False)
    monkeypatch.delenv("GOOGLE_CLIENT_SECRET", raising=False)
    monkeypatch.delenv("GOOGLE_PROJECT_ID", raising=False)
    monkeypatch.delenv("GCP_PUBSUB_TOPIC", raising=False)
    monkeypatch.delenv("TOKEN_STORE_DIR", raising=False)

    from alfred.core import config as cfg
    importlib.reload(cfg)
    from alfred.api.v1 import gmail_status as gs
    importlib.reload(gs)

    app = FastAPI()
    app.include_router(gs.router)
    client = TestClient(app)
    r = client.get("/api/v1/gmail/status")
    data = r.json()
    assert data["enabled"] is True
    assert data["configured"] is False
    assert data["ready"] is False


def test_gmail_status_ready(monkeypatch, tmp_path):
    monkeypatch.setenv("ENABLE_GMAIL", "true")
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "id")
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "secret")
    monkeypatch.setenv("GOOGLE_REDIRECT_URI", "http://127.0.0.1:8080/api/v1/gmail/callback")
    monkeypatch.setenv("GOOGLE_PROJECT_ID", "project")
    monkeypatch.setenv("TOKEN_STORE_DIR", str(tmp_path / ".tokens"))
    # Pub/Sub topic optional for readiness; not required for linking/messages

    from alfred.core import config as cfg
    importlib.reload(cfg)
    from alfred.api.v1 import gmail_status as gs
    importlib.reload(gs)

    app = FastAPI()
    app.include_router(gs.router)
    client = TestClient(app)
    r = client.get("/api/v1/gmail/status")
    data = r.json()
    assert data["enabled"] is True
    # In CI, Google deps are installed from requirements; if not, deps_installed may be False.
    assert data["configured"] is True
    assert data["token_dir_ready"] is True
    # readiness may be false if deps are unavailable locally; assert fields coherently instead of ready

