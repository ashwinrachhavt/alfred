"""Canvas API routes."""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

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
    """Generate Excalidraw diagram elements from natural language.

    Args:
        payload: The diagram request with prompt and optional canvas context.

    Returns:
        DiagramResponse with Excalidraw elements and description.
    """
    from alfred.core.llm_factory import get_chat_model
    from alfred.services.excalidraw_agent import build_diagram_prompt, parse_diagram_response

    # Build the prompt
    prompt = build_diagram_prompt(payload.prompt, payload.canvas_context)

    # Get the LLM and invoke it
    model = get_chat_model()
    response = model.invoke(prompt)

    # Extract content from response
    content = response.content if hasattr(response, "content") else str(response)

    # Parse the response into Excalidraw elements
    result = parse_diagram_response(content)

    return DiagramResponse(**result)
