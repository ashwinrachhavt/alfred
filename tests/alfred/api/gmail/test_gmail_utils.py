from alfred.api.gmail.routes import _truthy, gmail_status


def test_truthy_variants():
    assert _truthy(None) is False
    assert _truthy("1") is True
    assert _truthy(" true ") is True
    assert _truthy("Yes") is True
    assert _truthy("ON") is True
    assert _truthy("0") is False
    assert _truthy("no") is False
    assert _truthy("off") is False


def test_gmail_status_ready(monkeypatch, tmp_path):
    monkeypatch.setenv("ENABLE_GMAIL", "true")
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "abc")
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "def")
    monkeypatch.setenv("GOOGLE_REDIRECT_URI", "http://localhost:8000/callback")
    monkeypatch.setenv("GOOGLE_PROJECT_ID", "proj")
    monkeypatch.setenv("TOKEN_STORE_DIR", str(tmp_path))

    status = gmail_status()
    assert status["enabled"] is True
    assert status["configured"] is True
    assert status["token_dir_ready"] is True
    assert status["deps_installed"] is True
    assert status["ready"] is True


def test_gmail_status_not_configured(monkeypatch):
    # Enabled but missing essential config should not be ready
    monkeypatch.setenv("ENABLE_GMAIL", "true")
    for key in [
        "GOOGLE_CLIENT_ID",
        "GOOGLE_CLIENT_SECRET",
        "GOOGLE_REDIRECT_URI",
        "GOOGLE_PROJECT_ID",
        "TOKEN_STORE_DIR",
    ]:
        monkeypatch.delenv(key, raising=False)

    status = gmail_status()
    assert status["enabled"] is True
    assert status["configured"] is False
    assert status["token_dir_ready"] is False
    assert status["ready"] is False
