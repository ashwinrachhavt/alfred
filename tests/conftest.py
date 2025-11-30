"""Pytest configuration for Alfred.

Package is installed in editable mode (`pip install -e .` via `make install`),
so `import alfred` should resolve without path hacks.

This file also disables real network access during tests and clears provider
API keys to avoid accidental HTTP calls.
"""

from __future__ import annotations

import socket

import pytest


@pytest.fixture(autouse=True)
def _disable_network(monkeypatch: pytest.MonkeyPatch):
    """Disable outbound network calls during tests.

    Blocks low-level socket usage to prevent accidental HTTP egress.
    """

    # Block socket.create_connection (used by many HTTP clients)
    def _blocked_create_connection(*args, **kwargs):  # noqa: ANN001, ANN002
        raise RuntimeError("Network access is disabled during tests")

    monkeypatch.setattr(socket, "create_connection", _blocked_create_connection)

    # Harden: replace socket.socket.connect
    orig_socket = socket.socket

    class _GuardedSocket(orig_socket):  # type: ignore[misc]
        def connect(self, *args, **kwargs):  # noqa: ANN001, ANN002
            raise RuntimeError("Network access is disabled during tests")

    monkeypatch.setattr(socket, "socket", _GuardedSocket)


@pytest.fixture(autouse=True)
def _clear_provider_env(monkeypatch: pytest.MonkeyPatch):
    """Remove provider API keys/hosts so optional clients remain disabled."""

    for key in (
        "EXA_API_KEY",
        "TAVILY_API_KEY",
        "BRAVE_SEARCH_API_KEY",
        "YDC_API_KEY",
        "SEARXNG_HOST",
        "SEARX_HOST",
        "LANGSEARCH_API_KEY",
        "OPENAI_API_KEY",
    ):
        monkeypatch.delenv(key, raising=False)

    # Ensure tests don't attempt to enable Gmail integration
    monkeypatch.setenv("ENABLE_GMAIL", "0")
