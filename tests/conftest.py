from __future__ import annotations

import os
import socket
from typing import Any

import pytest

# Ensure the app runs in a unit-test-safe configuration during pytest collection.
# This prevents optional LLM modules (e.g. DSPy/OpenAI) from being enabled via a
# developer's local environment variables during unit tests.
os.environ.setdefault("APP_ENV", "test")


class NetworkBlockedError(RuntimeError):
    pass


def _blocked(*_args: Any, **_kwargs: Any) -> Any:
    raise NetworkBlockedError(
        "Network access is disabled during tests. "
        "Mark the test with @pytest.mark.integration/@pytest.mark.network or set ALLOW_NETWORK=1."
    )


@pytest.fixture(autouse=True)
def _disable_network(monkeypatch: pytest.MonkeyPatch, request: pytest.FixtureRequest) -> None:
    """Prevent accidental outbound network calls in unit tests."""

    if os.getenv("ALLOW_NETWORK") == "1":
        return

    if request.node.get_closest_marker("integration") or request.node.get_closest_marker("network"):
        return

    monkeypatch.setattr(socket, "create_connection", _blocked)
    monkeypatch.setattr(socket, "getaddrinfo", _blocked)
