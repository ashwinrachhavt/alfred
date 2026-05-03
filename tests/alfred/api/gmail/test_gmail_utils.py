from alfred.api.gmail.routes import gmail_status
from alfred.core.settings import settings


def test_gmail_status_ready(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "enable_gmail", True)
    monkeypatch.setattr(settings, "google_client_id", "abc")
    monkeypatch.setattr(settings, "google_client_secret", "def")
    monkeypatch.setattr(settings, "google_redirect_uri", "http://localhost:8000/callback")
    monkeypatch.setattr(settings, "google_project_id", "proj")
    monkeypatch.setattr(settings, "token_store_dir", str(tmp_path))

    status = gmail_status()
    assert status["enabled"] is True
    assert status["configured"] is True
    assert status["token_dir_ready"] is True
    assert status["deps_installed"] is True
    assert status["ready"] is True


def test_gmail_status_not_configured(monkeypatch):
    # Enabled but missing essential config should not be ready.
    monkeypatch.setattr(settings, "enable_gmail", True)
    monkeypatch.setattr(settings, "google_client_id", None)
    monkeypatch.setattr(settings, "google_client_secret", None)
    monkeypatch.setattr(settings, "google_redirect_uri", None)
    monkeypatch.setattr(settings, "google_project_id", None)
    monkeypatch.setattr(settings, "token_store_dir", "")

    status = gmail_status()
    assert status["enabled"] is True
    assert status["configured"] is False
    assert status["token_dir_ready"] is False
    assert status["ready"] is False
