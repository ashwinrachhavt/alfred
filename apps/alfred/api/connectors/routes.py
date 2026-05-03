from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter

from alfred.core.settings import settings
from alfred.services.notion_oauth import is_notion_oauth_configured, list_connected_workspaces

router = APIRouter(prefix="/api/connectors", tags=["connectors"])
logger = logging.getLogger(__name__)


def _has_value(value: object) -> bool:
    """True if a settings attribute holds a non-empty string or SecretStr."""
    if value is None:
        return False
    from pydantic import SecretStr
    if isinstance(value, SecretStr):
        return bool(value.get_secret_value().strip())
    return bool(str(value).strip())


def _all_have_value(*values: object) -> bool:
    return all(_has_value(v) for v in values)


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
    configured = _all_have_value(
        settings.google_client_id,
        settings.google_client_secret,
        settings.google_redirect_uri,
        settings.google_project_id,
    )
    token_dir_ready = _has_value(settings.token_store_dir)
    return {
        "connected": configured and token_dir_ready,
        "auth_type": "oauth",
        "details": {"configured": configured, "token_dir_ready": token_dir_ready},
    }


def _api_key_status(value: object) -> dict[str, Any]:
    return {
        "connected": _has_value(value),
        "auth_type": "api_key",
        "details": {},
    }


def _open_status() -> dict[str, Any]:
    return {"connected": True, "auth_type": "none", "details": {}}


_CONNECTOR_STATUS_MAP: dict[str, Any] = {
    # Knowledge
    "notion": _notion_status,
    "readwise": lambda: _api_key_status(settings.readwise_token),
    "pocket": lambda: _api_key_status(settings.pocket_access_token),
    "hypothesis": lambda: _api_key_status(settings.hypothesis_token),
    "arxiv": _open_status,
    "semantic_scholar": lambda: _api_key_status(settings.semantic_scholar_api_key),
    "wikipedia": _open_status,
    "rss": _open_status,
    "web": _open_status,
    # Productivity
    "gmail": lambda: _google_status("gmail"),
    "calendar": lambda: _google_status("calendar"),
    "gdrive": lambda: _google_status("gdrive"),
    "google_tasks": lambda: _google_status("google_tasks"),
    "github": lambda: _api_key_status(settings.github_token),
    "linear": lambda: _api_key_status(settings.linear_api_key),
    "todoist": lambda: _api_key_status(settings.todoist_token),
    "airtable": lambda: _api_key_status(settings.airtable_api_key),
    "slack": lambda: _api_key_status(settings.slack_api_key),
    # AI & Search
    "searxng": _open_status,
    "tavily": lambda: _api_key_status(settings.tavily_api_key),
    "brave_search": lambda: _api_key_status(settings.brave_api_key),
    "wolfram": lambda: _api_key_status(settings.wolfram_app_id),
    "exa": lambda: _api_key_status(settings.exa_api_key),
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
