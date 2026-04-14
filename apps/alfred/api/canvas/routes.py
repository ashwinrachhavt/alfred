"""Canvas API routes."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/canvas", tags=["canvas"])


class DiagramRequest(BaseModel):
    """Request to generate a diagram from natural language."""

    prompt: str
    canvas_context: str | None = None


class DiagramResponse(BaseModel):
    """Generated diagram elements and description."""

    elements: list[dict[str, Any]]
    description: str | None = None


def _response_to_text(response: Any) -> str:
    content = response.content if hasattr(response, "content") else response
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, dict) and isinstance(item.get("text"), str):
                parts.append(item["text"])
            else:
                parts.append(str(item))
        return "".join(parts)
    return str(content)


@router.post("/generate-diagram")
def generate_diagram(payload: DiagramRequest) -> dict:
    """Dispatch diagram generation to Celery, return task ID."""
    from alfred.core.celery_client import BrokerUnavailableError, dispatch_task
    from alfred.core.exceptions import ServiceUnavailableError

    try:
        task_result = dispatch_task(
            "canvas.generate_diagram",
            kwargs={"prompt": payload.prompt, "canvas_context": payload.canvas_context},
        )
        return {"task_id": task_result.id, "status": "pending"}
    except BrokerUnavailableError as exc:
        raise ServiceUnavailableError("Background worker unavailable") from exc
