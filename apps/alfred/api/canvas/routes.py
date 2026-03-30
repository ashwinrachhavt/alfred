"""Canvas API routes."""

from __future__ import annotations

import logging

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

    elements: list[dict]
    description: str | None = None


@router.post("/generate-diagram", response_model=DiagramResponse)
def generate_diagram(payload: DiagramRequest) -> DiagramResponse:
    """Generate Excalidraw diagram elements from natural language."""
    from alfred.core.llm_factory import get_chat_model
    from alfred.services.excalidraw_agent import build_diagram_prompt, parse_diagram_response

    try:
        prompt = build_diagram_prompt(payload.prompt, payload.canvas_context)
        model = get_chat_model()
        response = model.invoke(prompt)
        content = response.content if hasattr(response, "content") else str(response)
        result = parse_diagram_response(content)
        return DiagramResponse(**result)
    except Exception as exc:
        logger.warning("Diagram generation failed: %s", exc)
        return DiagramResponse(
            elements=[],
            description=f"Failed to generate diagram: {exc}",
        )
