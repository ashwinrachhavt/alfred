"""Canvas diagram generation offloaded to Celery."""
from __future__ import annotations

import logging

from celery import shared_task

_log = logging.getLogger(__name__)


@shared_task(name="canvas.generate_diagram")
def generate_diagram_task(*, prompt: str, canvas_context: str | None = None) -> dict:
    """Generate Excalidraw diagram elements from natural language prompt.

    This task offloads LLM-based diagram generation to avoid blocking FastAPI workers.
    The frontend polls for completion using the task_id.

    Args:
        prompt: User's natural language description of the diagram
        canvas_context: Optional JSON string of existing canvas elements

    Returns:
        Dict with "elements" (list of Excalidraw elements) and "description" (str)
    """
    from alfred.core.llm_factory import get_chat_model
    from alfred.services.excalidraw_agent import build_diagram_prompt, parse_diagram_response

    try:
        full_prompt = build_diagram_prompt(prompt, canvas_context)
        model = get_chat_model()
        response = model.invoke(full_prompt)
        content = response.content if hasattr(response, "content") else str(response)
        return parse_diagram_response(content)
    except Exception as exc:
        _log.warning("Diagram generation failed: %s", exc)
        return {"elements": [], "description": f"Failed: {exc}"}
