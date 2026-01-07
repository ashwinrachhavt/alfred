from __future__ import annotations

import threading
import time
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class OAuthStatePayload:
    """Metadata stored for an in-flight OAuth request."""

    scopes: list[str]
    namespaces: list[str | None]
    created_at: float
    expires_at: float


class OAuthStateStore:
    """In-memory TTL store for OAuth state.

    This is intentionally lightweight and avoids external dependencies so local
    development works without Redis. It is best-effort; in multi-worker
    deployments you should replace this with a shared store.
    """

    def __init__(self, *, ttl_seconds: int = 10 * 60) -> None:
        self._ttl_seconds = max(30, int(ttl_seconds))
        self._lock = threading.Lock()
        self._store: dict[str, OAuthStatePayload] = {}

    def put(self, state: str, *, scopes: list[str], namespaces: list[str | None]) -> None:
        now = time.time()
        payload = OAuthStatePayload(
            scopes=list(scopes),
            namespaces=list(namespaces),
            created_at=now,
            expires_at=now + self._ttl_seconds,
        )
        with self._lock:
            self._purge_locked(now)
            self._store[state] = payload

    def pop(self, state: str) -> OAuthStatePayload | None:
        now = time.time()
        with self._lock:
            self._purge_locked(now)
            payload = self._store.pop(state, None)
        if payload is None:
            return None
        if payload.expires_at <= now:
            return None
        return payload

    def _purge_locked(self, now: float) -> None:
        expired = [key for key, payload in self._store.items() if payload.expires_at <= now]
        for key in expired:
            self._store.pop(key, None)


_oauth_state_store = OAuthStateStore()


def save_oauth_state(state: str, *, scopes: list[str], namespaces: list[str | None]) -> None:
    """Persist an OAuth `state` value with associated metadata."""

    _oauth_state_store.put(state, scopes=scopes, namespaces=namespaces)


def consume_oauth_state(state: str) -> OAuthStatePayload | None:
    """Consume and remove the OAuth state payload if present."""

    return _oauth_state_store.pop(state)


__all__ = ["OAuthStatePayload", "consume_oauth_state", "save_oauth_state"]
