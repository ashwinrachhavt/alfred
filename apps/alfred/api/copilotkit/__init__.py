"""FastAPI wiring for CopilotKit remote access."""

import logging
from typing import Any

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from alfred.connectors.copilotkit import load_fastapi_endpoint
from alfred.services.copilotkit import get_copilotkit_remote_endpoint

COPILOTKIT_ROUTE = "/copilotkit_remote"


def register_copilotkit_endpoint(app: FastAPI, max_workers: int = 10) -> None:
    """Attach the CopilotKit remote endpoint to the FastAPI app."""
    add_fastapi_endpoint = load_fastapi_endpoint()

    if add_fastapi_endpoint is None:
        logging.getLogger(__name__).info(
            "CopilotKit integration skipped: optional dependency not installed."
        )
        return

    try:
        endpoint = get_copilotkit_remote_endpoint()
    except RuntimeError as exc:
        logging.getLogger(__name__).warning(
            "CopilotKit endpoint unavailable: %s", exc
        )
        return

    @app.get(f"{COPILOTKIT_ROUTE}/info", include_in_schema=False)
    async def copilotkit_info() -> JSONResponse:  # pragma: no cover - lightweight health helper
        """Provide agent/action metadata for simple health checks."""
        context: dict[str, Any] = {
            "properties": {},
            "frontend_url": None,
            "headers": {},
        }
        payload = endpoint.info(context=context)
        return JSONResponse(payload)

    add_fastapi_endpoint(app, endpoint, COPILOTKIT_ROUTE, max_workers=max_workers)


__all__ = ["register_copilotkit_endpoint", "COPILOTKIT_ROUTE"]
