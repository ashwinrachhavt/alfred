from __future__ import annotations

import logging
import os
from typing import Any

from fastapi import APIRouter

from alfred.core.settings import settings
from alfred.services.notion_oauth import is_notion_oauth_configured, list_connected_workspaces

router = APIRouter(prefix="/api/connectors", tags=["connectors"])
logger = logging.getLogger(__name__)


def _env_present(*keys: str) -> bool:
    """Return True if all env vars are non-empty."""
    return all((os.getenv(k) or "").strip() for k in keys)


def _notion_status() -> dict[str, Any]:
    env_token = bool(
        settings.notion_token is not None
        and settings.notion_token.get_secret_value().strip()
    )
    workspaces: list[dict[str, Any]] = []
    if is_notion_oauth_configured():
        try:
            workspaces = list_connected_workspaces()
        except Exception:
            pass
    connected = env_token or len(workspaces) > 0
    return {
        "connected": connected,
        "auth_type": "oauth",
        "details": {
            "workspaces": workspaces,
            "env_token": env_token,
        },
    }


def _google_status(service: str) -> dict[str, Any]:
    configured = _env_present(
        "GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET",
        "GOOGLE_REDIRECT_URI", "GOOGLE_PROJECT_ID",
    )
    token_dir = (os.getenv("TOKEN_STORE_DIR") or "").strip()
    return {
        "connected": configured and bool(token_dir),
        "auth_type": "oauth",
        "details": {"configured": configured, "token_dir_ready": bool(token_dir)},
    }


def _api_key_status(env_var: str) -> dict[str, Any]:
    present = _env_present(env_var)
    return {
        "connected": present,
        "auth_type": "api_key",
        "details": {},
    }


def _open_status() -> dict[str, Any]:
    return {"connected": True, "auth_type": "none", "details": {}}


_CONNECTOR_STATUS_MAP: dict[str, Any] = {
    # Knowledge
    "notion": _notion_status,
    "readwise": lambda: _api_key_status("READWISE_TOKEN"),
    "pocket": lambda: _api_key_status("POCKET_ACCESS_TOKEN"),
    "hypothesis": lambda: _api_key_status("HYPOTHESIS_TOKEN"),
    "arxiv": _open_status,
    "semantic_scholar": lambda: _api_key_status("SEMANTIC_SCHOLAR_API_KEY"),
    "wikipedia": _open_status,
    "rss": _open_status,
    "web": _open_status,
    # Productivity
    "gmail": lambda: _google_status("gmail"),
    "calendar": lambda: _google_status("calendar"),
    "gdrive": lambda: _google_status("gdrive"),
    "google_tasks": lambda: _google_status("google_tasks"),
    "github": lambda: _api_key_status("GITHUB_TOKEN"),
    "linear": lambda: _api_key_status("LINEAR_API_KEY"),
    "todoist": lambda: _api_key_status("TODOIST_TOKEN"),
    "airtable": lambda: _api_key_status("AIRTABLE_API_KEY"),
    "slack": lambda: _api_key_status("SLACK_API_KEY"),
    # AI & Search
    "searxng": _open_status,
    "tavily": lambda: _api_key_status("TAVILY_API_KEY"),
    "brave_search": lambda: _api_key_status("BRAVE_API_KEY"),
    "wolfram": lambda: _api_key_status("WOLFRAM_APP_ID"),
    "exa": lambda: _api_key_status("EXA_API_KEY"),
}


@router.get("/status-all")
def connectors_status_all() -> dict[str, Any]:
    """Return aggregated status for all known connectors."""
    result: dict[str, Any] = {}
    for key, fn in _CONNECTOR_STATUS_MAP.items():
        try:
            result[key] = fn() if callable(fn) else fn
        except Exception as exc:
            logger.warning("Failed to get status for %s: %s", key, exc)
            result[key] = {"connected": False, "auth_type": "unknown", "error": str(exc)}
    return {"connectors": result}
