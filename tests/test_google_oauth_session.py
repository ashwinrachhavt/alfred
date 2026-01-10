from __future__ import annotations

import asyncio
import json
import threading
import time
from datetime import datetime, timedelta, timezone

import pytest
from alfred.connectors.google_oauth_session import GoogleOAuthSession
from alfred.services.google_oauth import persist_credentials, token_path
from google.oauth2.credentials import Credentials


@pytest.mark.asyncio
async def test_google_oauth_session_refresh_is_single_flight(monkeypatch: pytest.MonkeyPatch) -> None:
    refresh_calls = 0
    refresh_calls_lock = threading.Lock()

    def fake_refresh(self: Credentials, _request: object) -> None:
        nonlocal refresh_calls
        with refresh_calls_lock:
            refresh_calls += 1
        time.sleep(0.05)
        self.token = "refreshed-token"
        self.expiry = datetime.now(timezone.utc) + timedelta(minutes=30)

    monkeypatch.setattr(Credentials, "refresh", fake_refresh, raising=True)

    creds = Credentials(
        token="stale-token",
        refresh_token="refresh-token",
        token_uri="https://oauth2.googleapis.com/token",
        client_id="client-id",
        client_secret="client-secret",
        scopes=["https://www.googleapis.com/auth/gmail.readonly"],
        expiry=datetime.now(timezone.utc) - timedelta(seconds=1),
    )

    session = GoogleOAuthSession(creds)
    refreshed_a, refreshed_b = await asyncio.gather(
        session.get_credentials(),
        session.get_credentials(),
    )

    assert refreshed_a.token == "refreshed-token"
    assert refreshed_b.token == "refreshed-token"
    assert refresh_calls == 1


def test_persist_credentials_writes_valid_json(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "alfred.services.google_oauth.settings.token_store_dir",
        str(tmp_path),
    )

    creds = Credentials(
        token="token",
        refresh_token="refresh-token",
        token_uri="https://oauth2.googleapis.com/token",
        client_id="client-id",
        client_secret="client-secret",
        scopes=["https://www.googleapis.com/auth/gmail.readonly"],
        expiry=datetime.now(timezone.utc) + timedelta(minutes=30),
    )

    persist_credentials(None, creds, namespace="gmail")
    p = token_path(None, namespace="gmail")

    payload = json.loads(p.read_text(encoding="utf-8"))
    assert payload.get("token") == "token"

    # Atomic write should not leave tmp artifacts behind.
    assert [child.name for child in tmp_path.iterdir()] == [p.name]


def test_token_path_sanitizes_user_and_namespace(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "alfred.services.google_oauth.settings.token_store_dir",
        str(tmp_path),
    )

    p = token_path("../user-id", namespace="../gmail")

    assert p.parent == tmp_path
    assert ".." not in p.name
    assert "/" not in p.name
