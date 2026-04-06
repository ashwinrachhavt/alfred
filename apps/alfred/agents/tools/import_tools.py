"""Import agent tools -- connector management and import orchestration.

Tools for running imports from external sources, checking task status,
and listing available connectors.
"""

from __future__ import annotations

import json
import logging

from langchain_core.tools import tool

logger = logging.getLogger(__name__)

# Registry of available connectors
AVAILABLE_CONNECTORS = [
    "notion",
    "readwise",
    "google_calendar",
    "google_gmail",
    "google_drive",
    "google_tasks",
    "github",
    "linear",
    "hypothesis",
    "pocket",
    "airtable",
    "todoist",
    "slack",
]


@tool
def list_connectors() -> str:
    """List all available import connectors. Returns connector names and their status."""
    connectors_info = []
    for name in AVAILABLE_CONNECTORS:
        # Check if connector is configured (has required env vars)
        configured = _check_connector_configured(name)
        connectors_info.append({
            "name": name,
            "configured": configured,
            "display_name": name.replace("_", " ").title(),
        })
    return json.dumps(connectors_info)


def _check_connector_configured(connector_name: str) -> bool:
    """Check if a connector has required environment variables set."""
    try:
        from alfred.core.settings import settings

        # Map connector names to their required settings
        required_settings = {
            "notion": lambda: bool(settings.notion_token),
            "readwise": lambda: bool(settings.readwise_token),
            "google_calendar": lambda: bool(settings.google_oauth_client_id),
            "google_gmail": lambda: bool(settings.google_oauth_client_id),
            "google_drive": lambda: bool(settings.google_oauth_client_id),
            "google_tasks": lambda: bool(settings.google_oauth_client_id),
            "github": lambda: bool(settings.github_token),
            "linear": lambda: bool(settings.linear_api_key),
            "hypothesis": lambda: True,  # Public API, no key required
            "pocket": lambda: bool(settings.pocket_consumer_key),
            "airtable": lambda: bool(settings.airtable_api_key),
            "todoist": lambda: bool(settings.todoist_api_key),
            "slack": lambda: bool(settings.slack_bot_token),
        }

        checker = required_settings.get(connector_name)
        if not checker:
            return False
        return checker()
    except Exception:
        return False


@tool
def run_import(connector_name: str, incremental: bool = True, limit: int | None = None) -> str:
    """Run an import from a specified connector. Returns task ID for status tracking."""
    if connector_name not in AVAILABLE_CONNECTORS:
        return json.dumps({
            "error": f"Unknown connector: {connector_name}",
            "available": AVAILABLE_CONNECTORS,
        })

    if not _check_connector_configured(connector_name):
        return json.dumps({
            "error": f"Connector '{connector_name}' is not configured",
            "hint": "Check required environment variables are set",
        })

    try:
        # Dynamically import and run the appropriate task
        if connector_name == "notion":
            from alfred.tasks.notion_import import notion_import_task
            result = notion_import_task.delay(incremental=incremental)
            return json.dumps({
                "ok": True,
                "connector": connector_name,
                "task_id": result.id,
                "status": "queued",
            })
        else:
            # For other connectors, we'd need to implement similar tasks
            # For now, return a stub response
            return json.dumps({
                "error": f"Import task not implemented for {connector_name}",
                "status": "not_implemented",
            })
    except Exception as exc:
        logger.error("run_import failed for %s: %s", connector_name, exc)
        return json.dumps({"error": str(exc)})


@tool
def import_status(task_id: str) -> str:
    """Check the status of an import task by task ID. Returns state, progress, and result if complete."""
    try:
        from celery.result import AsyncResult

        from alfred.core.celery import celery_app

        result = AsyncResult(task_id, app=celery_app)

        response = {
            "task_id": task_id,
            "state": result.state,
            "ready": result.ready(),
        }

        if result.ready():
            if result.successful():
                response["result"] = result.result
            else:
                response["error"] = str(result.info)
        else:
            # Check for progress info (if task is reporting progress)
            if result.info and isinstance(result.info, dict):
                response["progress"] = result.info

        return json.dumps(response)
    except Exception as exc:
        logger.error("import_status failed: %s", exc)
        return json.dumps({"error": str(exc)})


# List of all import tools for agent registration
IMPORT_TOOLS = [list_connectors, run_import, import_status]
