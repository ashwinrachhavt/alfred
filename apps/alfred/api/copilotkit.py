"""FastAPI wiring for CopilotKit remote access."""

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from copilotkit.integrations.fastapi import add_fastapi_endpoint

from alfred.services.copilotkit import get_copilotkit_remote_endpoint


COPILOTKIT_ROUTE = "/copilotkit_remote"


def register_copilotkit_endpoint(app: FastAPI, max_workers: int = 10) -> None:
    """Attach the CopilotKit remote endpoint to the FastAPI app."""
    endpoint = get_copilotkit_remote_endpoint()
    @app.get(f"{COPILOTKIT_ROUTE}/info", include_in_schema=False)
    async def copilotkit_info() -> JSONResponse:
        """Provide agent/action metadata for simple health checks."""
        context = {
            "properties": {},
            "frontend_url": None,
            "headers": {},
        }
        payload = endpoint.info(context=context)
        return JSONResponse(payload)

    add_fastapi_endpoint(app, endpoint, COPILOTKIT_ROUTE, max_workers=max_workers)
