"""FastAPI wiring for CopilotKit remote access."""

import logging
from typing import Any

try:  # pragma: no cover - optional dependency
    from copilotkit.integrations.fastapi import add_fastapi_endpoint
except ModuleNotFoundError:  # pragma: no cover
    add_fastapi_endpoint = None  # type: ignore[assignment]

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from alfred.services.copilotkit import get_copilotkit_remote_endpoint

COPILOTKIT_ROUTE = "/copilotkit_remote"


def register_copilotkit_endpoint(app: FastAPI, max_workers: int = 10) -> None:
    """Attach the CopilotKit remote endpoint to the FastAPI app."""
    if add_fastapi_endpoint is None:
        logging.getLogger(__name__).info(
            "CopilotKit integration skipped: optional dependency not installed."
        )
        return

    endpoint = get_copilotkit_remote_endpoint()

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
