from __future__ import annotations

import os

from fastapi import APIRouter

router = APIRouter(prefix="/api/v1/gmail", tags=["gmail"])


def _truthy(val: str | None) -> bool:
    if val is None:
        return False
    return val.strip().lower() in {"1", "true", "yes", "on"}


def _deps_installed() -> bool:
    try:
        return True
    except Exception:
        return False


@router.get("/status")
def gmail_status():
    enabled = _truthy(os.getenv("ENABLE_GMAIL", "false"))

    client_id = os.getenv("GOOGLE_CLIENT_ID", "")
    client_secret = os.getenv("GOOGLE_CLIENT_SECRET", "")
    redirect_uri = os.getenv("GOOGLE_REDIRECT_URI", "")
    project_id = os.getenv("GOOGLE_PROJECT_ID", "")
    token_dir = os.getenv("TOKEN_STORE_DIR", "")

    configured = all([client_id, client_secret, redirect_uri, project_id])
    # Consider ready if a directory is configured; the app can create it on first use.
    token_dir_ready = bool(token_dir)
    deps_ok = _deps_installed()

    ready = enabled and configured and deps_ok and token_dir_ready

    return {
        "enabled": enabled,
        "configured": configured,
        "deps_installed": deps_ok,
        "token_dir_ready": token_dir_ready,
        "ready": ready,
    }
