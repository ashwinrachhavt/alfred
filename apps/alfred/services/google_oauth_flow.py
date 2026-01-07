from __future__ import annotations

from typing import Any

from google.oauth2.credentials import Credentials

from alfred.services.google_oauth import exchange_code_for_tokens, persist_credentials
from alfred.services.oauth_state import consume_oauth_state


def complete_google_oauth(
    *,
    code: str,
    state: str | None,
    fallback_scopes: list[str],
    fallback_namespaces: list[str | None],
    user_id: str | None = None,
) -> dict[str, Any]:
    """Exchange an OAuth code for tokens and persist them.

    If `state` matches an entry in the in-memory OAuth state store, its scopes
    and namespaces override the provided fallbacks.
    """

    resolved_scopes = fallback_scopes
    resolved_namespaces = fallback_namespaces
    if state:
        stored = consume_oauth_state(state)
        if stored is not None:
            resolved_scopes = stored.scopes
            resolved_namespaces = stored.namespaces

    namespaces = list(resolved_namespaces) if resolved_namespaces else [None]
    primary = namespaces[0]

    creds: Credentials = exchange_code_for_tokens(
        user_id=user_id,
        code=code,
        state=state,
        scopes=resolved_scopes,
        namespace=primary,
    )

    for namespace in namespaces[1:]:
        persist_credentials(user_id, creds, namespace=namespace)

    return {
        "ok": True,
        "namespaces": namespaces,
        "scopes": list(creds.scopes or []),
        "has_refresh_token": bool(getattr(creds, "refresh_token", None)),
    }


__all__ = ["complete_google_oauth"]
